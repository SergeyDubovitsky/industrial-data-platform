from __future__ import annotations

import json
import os
import subprocess
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from idp_config_registry.application.use_cases.render_config import (
    RenderAgentRuntimeConfig,
    RenderAgentRuntimeConfigCommand,
    StoreRenderedAgentRuntimeConfig,
)
from idp_config_registry.domain.entities import ConfigOutboxRecord
from idp_config_registry.infrastructure.json_schema_validator import (
    JsonSchemaConfigPayloadValidator,
)
from idp_config_registry.infrastructure.kafka.config_delivery import (
    ConfluentKafkaConfigRecordPublisher,
)
from idp_config_registry.infrastructure.postgres.unit_of_work import (
    PostgresUnitOfWorkFactory,
)
from idp_config_registry.main import create_app
from idp_config_registry.settings import ConfigRegistrySettings

pytestmark = [
    pytest.mark.integration,
    pytest.mark.integration_config_delivery,
    pytest.mark.integration_data_platform,
]

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_DIR = REPO_ROOT / "docs" / "contracts" / "edge-telemetry-agent" / "schemas"
DEMO_BUNDLE_PATH = (
    REPO_ROOT / "environments" / "demo-stand" / "edge_telemetry_agent" / "config.bundle.yaml"
)


@pytest.mark.integration_smoke
@pytest.mark.asyncio
async def test_config_registry_kafka_publisher_writes_config_delivery_record(
    local_platform_stack,
) -> None:
    record = ConfigOutboxRecord.new(
        tenant_id="tenant-a",
        idempotency_key="tenant-a|asset-a|agent-a|rev-001|agent_runtime",
        asset_id="asset-a",
        agent_id="agent-a",
        config_revision="rev-001",
        config_scope="agent_runtime",
        source_id=None,
        source_config_revision=None,
        kafka_key="tenant-a|asset-a|agent-a|agent_runtime",
        payload_json={
            "message_type": "idp.edge.config.delivery.v1",
            "tenant_id": "tenant-a",
            "asset_id": "asset-a",
            "agent_id": "agent-a",
            "config_revision": "rev-001",
            "config_scope": "agent_runtime",
            "source_id": None,
            "source_config_revision": None,
            "target_mqtt_topic": "idp/v1/agents/agent-a/config/agent-runtime",
            "mqtt_retain": True,
            "mqtt_qos": 1,
            "operation": "upsert",
            "payload_message_type": "idp.edge.agent-runtime-config.v1",
            "payload": {
                "message_type": "idp.edge.agent-runtime-config.v1",
                "tenant_id": "tenant-a",
                "asset_id": "asset-a",
                "agent_id": "agent-a",
                "config_revision": "rev-001",
                "issued_at": "2026-05-03T10:00:00Z",
                "sources": [
                    {
                        "source_id": "knx-main",
                        "source_config_revision": "rev-001-knx-main",
                        "enabled": True,
                    }
                ],
            },
            "idempotency_key": "tenant-a|asset-a|agent-a|rev-001|agent_runtime",
            "issued_at": "2026-05-03T10:00:00Z",
        },
    )
    publisher = ConfluentKafkaConfigRecordPublisher.from_bootstrap_servers(
        f"127.0.0.1:{local_platform_stack.kafka_port}",
        client_id="idp-config-registry-it",
    )

    await publisher.publish(record)

    key, payload = local_platform_stack.consume_kafka_json(
        "idp.edge.configs.v1",
        expected_key="tenant-a|asset-a|agent-a|agent_runtime",
        timeout=30,
    )

    assert key == "tenant-a|asset-a|agent-a|agent_runtime"
    assert payload["message_type"] == "idp.edge.config.delivery.v1"
    assert payload["tenant_id"] == "tenant-a"
    assert payload["config_scope"] == "agent_runtime"
    assert payload["target_mqtt_topic"] == "idp/v1/agents/agent-a/config/agent-runtime"
    assert payload["payload"]["message_type"] == "idp.edge.agent-runtime-config.v1"


@pytest.mark.asyncio
async def test_config_registry_cli_publishes_outbox_batch_to_kafka(
    local_platform_stack,
    local_config_registry_postgres_stack,
) -> None:
    settings = ConfigRegistrySettings(
        database_url=local_config_registry_postgres_stack.database_url
    )
    with TestClient(create_app(settings=settings)) as client:
        _create_renderable_agent_graph(client)

    unit_of_work_factory = PostgresUnitOfWorkFactory.from_url(settings.database_url)
    validator = JsonSchemaConfigPayloadValidator.from_contract_dir(CONTRACT_DIR)
    try:
        rendered = await RenderAgentRuntimeConfig(unit_of_work_factory(), validator).execute(
            RenderAgentRuntimeConfigCommand(
                tenant_id="tenant-cli",
                asset_id="asset-a",
                agent_id="agent-a",
                config_revision="rev-cli-001",
                issued_at=datetime(2026, 5, 3, 10, 0, tzinfo=UTC),
                source_config_revisions={"knx-main": "rev-cli-001-knx-main"},
            )
        )
        await StoreRenderedAgentRuntimeConfig(unit_of_work_factory(), validator).execute(
            rendered
        )
    finally:
        await unit_of_work_factory.dispose()

    env = os.environ.copy()
    env.update(
        {
            "CONFIG_REGISTRY_DATABASE_URL": (
                local_config_registry_postgres_stack.database_url
            ),
            "KAFKA_BOOTSTRAP_SERVERS": f"127.0.0.1:{local_platform_stack.kafka_port}",
            "CONFIG_REGISTRY_KAFKA_CLIENT_ID": "idp-config-registry-cli-it",
        }
    )
    result = subprocess.run(
        [
            "uv",
            "run",
            "--frozen",
            "--package",
            "idp-config-registry",
            "idp-config-registry",
            "publish-config-outbox-once",
            "--limit",
            "10",
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )

    assert result.returncode == 0, result.stderr
    assert "published=2" in result.stdout
    runtime_key, agent_runtime_payload = local_platform_stack.consume_kafka_json(
        "idp.edge.configs.v1",
        expected_key="tenant-cli|asset-a|agent-a|agent_runtime",
        timeout=30,
    )

    assert runtime_key == "tenant-cli|asset-a|agent-a|agent_runtime"
    assert agent_runtime_payload["config_scope"] == "agent_runtime"


def test_config_outbox_worker_container_publishes_records_to_kafka_and_mqtt(
    local_config_delivery_stack,
) -> None:
    _create_renderable_agent_graph_via_api(
        local_config_delivery_stack,
        tenant_id="tenant-worker",
    )
    rendered = local_config_delivery_stack.config_registry_json(
        "POST",
        "/tenants/tenant-worker/assets/asset-a/agents/agent-a/render-config",
        {
            "config_revision": "rev-worker-001",
            "issued_at": "2026-05-03T10:00:00Z",
            "source_config_revisions": {"knx-main": "rev-worker-001-knx-main"},
        },
    )

    runtime_key, agent_runtime_payload = local_config_delivery_stack.consume_kafka_json(
        "idp.edge.configs.v1",
        expected_key="tenant-worker|asset-a|agent-a|agent_runtime",
        timeout=60,
    )
    runtime_message = local_config_delivery_stack.wait_for_retained_mqtt_json(
        "idp/v1/agents/agent-a/config/agent-runtime",
        predicate=lambda message: message.payload.get("tenant_id")
        == "tenant-worker",
        timeout=60,
    )
    source_snapshot_key, source_snapshot = (
        local_config_delivery_stack.consume_kafka_json(
            "idp.source.configs.v1",
            expected_key="tenant-worker|asset-a|agent-a|knx-main",
            timeout=60,
        )
    )

    assert rendered["outbox_record_count"] == 2
    assert runtime_key == "tenant-worker|asset-a|agent-a|agent_runtime"
    assert agent_runtime_payload["message_type"] == "idp.edge.config.delivery.v1"
    assert agent_runtime_payload["config_scope"] == "agent_runtime"
    assert agent_runtime_payload["payload"]["message_type"] == "idp.edge.agent-runtime-config.v1"
    assert runtime_message.payload["message_type"] == "idp.edge.agent-runtime-config.v1"
    assert runtime_message.payload["tenant_id"] == "tenant-worker"
    assert runtime_message.payload["config_revision"] == "rev-worker-001"
    assert source_snapshot_key == "tenant-worker|asset-a|agent-a|knx-main"
    assert source_snapshot["message_type"] == "idp.source.config.v1"
    assert source_snapshot["source_config_revision"] == "rev-worker-001-knx-main"


@pytest.mark.integration_smoke
def test_config_registry_api_container_uses_local_postgres(
    local_config_delivery_stack,
) -> None:
    health = local_config_delivery_stack.config_registry_json("GET", "/health")
    backoffice_url = (
        f"http://127.0.0.1:{local_config_delivery_stack.config_registry_port}"
        "/backoffice/"
    )
    legacy_render_config_url = (
        f"http://127.0.0.1:{local_config_delivery_stack.config_registry_port}"
        "/backoffice/render-config"
    )
    agent_list_url = (
        f"http://127.0.0.1:{local_config_delivery_stack.config_registry_port}"
        "/backoffice/agent-model/list"
    )
    created = local_config_delivery_stack.config_registry_json(
        "POST",
        "/tenants",
        {"tenant_id": "tenant-api-container", "name": "Tenant API Container"},
    )
    local_config_delivery_stack.config_registry_json(
        "POST",
        "/tenants/tenant-api-container/assets",
        {"asset_id": "asset-api-container", "name": "Asset API Container"},
    )
    local_config_delivery_stack.config_registry_json(
        "POST",
        "/tenants/tenant-api-container/assets/asset-api-container/agents",
        {"agent_id": "agent-api-container", "name": "Agent API Container"},
    )
    tenants = local_config_delivery_stack.config_registry_json("GET", "/tenants")
    with urllib.request.urlopen(backoffice_url, timeout=10) as response:
        backoffice_status = response.status
        backoffice_html = response.read().decode()
    with urllib.request.urlopen(agent_list_url, timeout=10) as response:
        agent_list_status = response.status
        agent_list_html = response.read().decode()
    with pytest.raises(urllib.error.HTTPError) as legacy_render_config_error:
        urllib.request.urlopen(legacy_render_config_url, timeout=10)

    assert health == {"status": "ok"}
    assert backoffice_status == 200
    assert agent_list_status == 200
    assert "Config Registry Backoffice" in backoffice_html
    assert "Собрать config" in agent_list_html
    assert "render-agent-config" in agent_list_html
    assert legacy_render_config_error.value.code == 404
    assert created["tenant_id"] == "tenant-api-container"
    assert any(
        tenant["tenant_id"] == "tenant-api-container"
        for tenant in tenants
        if isinstance(tenant, dict)
    )


def test_redpanda_connect_projects_config_delivery_records_to_retained_mqtt(
    local_platform_stack,
) -> None:
    runtime_record = {
        "message_type": "idp.edge.config.delivery.v1",
        "tenant_id": "tenant-projection",
        "asset_id": "asset-a",
        "agent_id": "agent-a",
        "config_revision": "rev-projection-001",
        "config_scope": "agent_runtime",
        "source_id": None,
        "source_config_revision": None,
        "target_mqtt_topic": "idp/v1/agents/agent-a/config/agent-runtime",
        "mqtt_retain": True,
        "mqtt_qos": 1,
        "operation": "upsert",
        "payload_message_type": "idp.edge.agent-runtime-config.v1",
        "payload": {
            "message_type": "idp.edge.agent-runtime-config.v1",
            "tenant_id": "tenant-projection",
            "asset_id": "asset-a",
            "agent_id": "agent-a",
            "config_revision": "rev-projection-001",
            "issued_at": "2026-05-03T10:00:00Z",
            "sources": [
                {
                    "source_id": "knx-main",
                    "source_config_revision": "rev-projection-001-knx-main",
                    "enabled": True,
                }
            ],
        },
        "idempotency_key": "tenant-projection|asset-a|agent-a|rev-projection-001|agent_runtime",
        "issued_at": "2026-05-03T10:00:00Z",
    }
    source_record = {
        "message_type": "idp.edge.config.delivery.v1",
        "tenant_id": "tenant-projection",
        "asset_id": "asset-a",
        "agent_id": "agent-a",
        "config_revision": "rev-projection-001",
        "config_scope": "source:knx-main",
        "source_id": "knx-main",
        "source_config_revision": "rev-projection-001-knx-main",
        "target_mqtt_topic": "idp/v1/agents/agent-a/sources/knx-main/config",
        "mqtt_retain": True,
        "mqtt_qos": 1,
        "operation": "upsert",
        "payload_message_type": "idp.edge.source-config.v1",
        "payload": {
            "message_type": "idp.edge.source-config.v1",
            "tenant_id": "tenant-projection",
            "asset_id": "asset-a",
            "agent_id": "agent-a",
            "source_id": "knx-main",
            "source_type": "knx",
            "config_revision": "rev-projection-001",
            "source_config_revision": "rev-projection-001-knx-main",
            "enabled": True,
            "connection": {"gateway_ip": "127.0.0.1"},
            "acquisition_defaults": {
                "listen": True,
                "read_on_start": False,
                "periodic_interval_seconds": None,
            },
            "publish_defaults": {
                "enabled": True,
                "change_threshold": None,
            },
            "points": [
                {
                    "point_key": "temperature",
                    "point_ref": "2/0/0",
                    "name": "Temperature",
                    "value_type": "number",
                    "value_model": "knx.dpt.9.001",
                    "signal_type": "sensor",
                    "acquisition": {
                        "listen": True,
                        "read_on_start": True,
                        "periodic_interval_seconds": None,
                    },
                    "publish": {
                        "enabled": True,
                        "change_threshold": 1.0,
                    },
                    "tags": {"room": "demo"},
                }
            ],
        },
        "idempotency_key": "tenant-projection|asset-a|agent-a|rev-projection-001|source:knx-main",
        "issued_at": "2026-05-03T10:00:00Z",
    }

    local_platform_stack.produce_kafka_text(
        "idp.edge.configs.v1",
        json.dumps(runtime_record),
        key="tenant-projection|asset-a|agent-a|agent_runtime",
    )
    local_platform_stack.produce_kafka_text(
        "idp.edge.configs.v1",
        json.dumps(source_record),
        key="tenant-projection|asset-a|agent-a|source:knx-main",
    )

    runtime_message = local_platform_stack.wait_for_retained_mqtt_json(
        "idp/v1/agents/agent-a/config/agent-runtime",
        predicate=lambda message: message.payload.get("tenant_id")
        == "tenant-projection",
        timeout=45,
    )
    source_message = local_platform_stack.wait_for_retained_mqtt_json(
        "idp/v1/agents/agent-a/sources/knx-main/config",
        predicate=lambda message: message.payload.get("tenant_id")
        == "tenant-projection",
        timeout=45,
    )

    assert runtime_message.retained is True
    assert runtime_message.payload["message_type"] == "idp.edge.agent-runtime-config.v1"
    assert runtime_message.payload["tenant_id"] == "tenant-projection"
    assert runtime_message.payload["config_revision"] == "rev-projection-001"
    assert source_message.retained is True
    assert source_message.payload["message_type"] == "idp.edge.source-config.v1"
    assert source_message.payload["source_id"] == "knx-main"
    assert (
        source_message.payload["source_config_revision"]
        == "rev-projection-001-knx-main"
    )

    source_snapshot_key, source_snapshot = local_platform_stack.consume_kafka_json(
        "idp.source.configs.v1",
        expected_key="tenant-projection|asset-a|agent-a|knx-main",
        timeout=45,
    )

    assert source_snapshot_key == "tenant-projection|asset-a|agent-a|knx-main"
    assert source_snapshot["message_type"] == "idp.source.config.v1"
    assert source_snapshot["tenant_id"] == "tenant-projection"
    assert source_snapshot["source_config_revision"] == "rev-projection-001-knx-main"
    assert source_snapshot["points"][0]["point_id"] == (
        "tenant-projection|asset-a|knx-main|temperature"
    )


def test_publish_edge_demo_cli_seeds_config_through_config_registry_api_by_default(
    local_config_delivery_stack,
) -> None:
    env = os.environ.copy()
    env.update(
        {
            "MQTT_BROKER": f"mqtt://127.0.0.1:{local_config_delivery_stack.mqtt_port}",
            "MQTT_USERNAME": local_config_delivery_stack.mqtt_username,
            "MQTT_PASSWORD": local_config_delivery_stack.mqtt_password,
            "CONFIG_REGISTRY_URL": (
                f"http://127.0.0.1:{local_config_delivery_stack.config_registry_port}"
            ),
            "KNX_LOCAL_GATEWAY_IP": "127.0.0.1",
            "KNX_LOCAL_GATEWAY_PORT": "3671",
            "KNX_LOCAL_ROUTE_BACK": "false",
        }
    )

    result = subprocess.run(
        [
            "uv",
            "run",
            "--frozen",
            "--package",
            "idp-demo-stack",
            "publish-edge-demo",
            "--bundle-config",
            str(DEMO_BUNDLE_PATH),
            "--count",
            "1",
            "--interval-seconds",
            "0",
            "--retained-refresh-seconds",
            "0",
            "--no-status",
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=90,
    )

    assert result.returncode == 0, result.stderr
    assert "CONFIG_REGISTRY_UPSERTED " in result.stdout
    assert "CONFIG_REGISTRY_RENDERED " in result.stdout
    assert "RETAINED_CONFIG_READY topics=2" in result.stdout
    assert "PUBLISHED_CONFIG_DELIVERY records=2" not in result.stdout
    runtime_message = local_config_delivery_stack.wait_for_retained_mqtt_json(
        "idp/v1/agents/demo-stand-local/config/agent-runtime",
        timeout=45,
    )
    source_message = local_config_delivery_stack.wait_for_retained_mqtt_json(
        "idp/v1/agents/demo-stand-local/sources/knx_main/config",
        timeout=45,
    )

    assert runtime_message.retained is True
    assert runtime_message.payload["message_type"] == "idp.edge.agent-runtime-config.v1"
    assert runtime_message.payload["config_revision"] == "rev-demo-stand-001"
    assert source_message.retained is True
    assert source_message.payload["source_config_revision"] == (
        "rev-demo-stand-knx-main-001"
    )


def _create_renderable_agent_graph(
    client: TestClient,
    *,
    tenant_id: str = "tenant-cli",
) -> None:
    client.post(
        "/tenants",
        json={"tenant_id": tenant_id, "name": "Tenant CLI"},
    )
    client.post(
        f"/tenants/{tenant_id}/assets",
        json={"asset_id": "asset-a", "name": "Asset A"},
    )
    client.post(
        f"/tenants/{tenant_id}/assets/asset-a/agents",
        json={"agent_id": "agent-a"},
    )
    client.post(
        f"/tenants/{tenant_id}/assets/asset-a/agents/agent-a/sources",
        json={
            "source_id": "knx-main",
            "source_type": "knx",
            "connection_json": {"gateway_ip": "127.0.0.1"},
            "acquisition_defaults_json": {
                "listen": True,
                "read_on_start": False,
                "periodic_interval_seconds": None,
            },
            "publish_defaults_json": {
                "enabled": True,
                "change_threshold": None,
            },
        },
    )
    client.post(
        f"/tenants/{tenant_id}/assets/asset-a/agents/agent-a"
        "/sources/knx-main/points",
        json={
            "point_id": f"{tenant_id}|asset-a|knx-main|temperature",
            "point_key": "temperature",
            "point_ref": "2/0/0",
            "name": "Temperature",
            "value_type": "number",
            "value_model": "knx.dpt.9.001",
            "signal_type": "sensor",
            "acquisition_json": {"read_on_start": True},
            "publish_json": {"change_threshold": 1.0},
            "tags_json": {"room": "demo"},
        },
    )


def _create_renderable_agent_graph_via_api(
    stack,
    *,
    tenant_id: str,
) -> None:
    stack.config_registry_json(
        "POST",
        "/tenants",
        {"tenant_id": tenant_id, "name": "Tenant Worker"},
    )
    stack.config_registry_json(
        "POST",
        f"/tenants/{tenant_id}/assets",
        {"asset_id": "asset-a", "name": "Asset A"},
    )
    stack.config_registry_json(
        "POST",
        f"/tenants/{tenant_id}/assets/asset-a/agents",
        {"agent_id": "agent-a"},
    )
    stack.config_registry_json(
        "POST",
        f"/tenants/{tenant_id}/assets/asset-a/agents/agent-a/sources",
        {
            "source_id": "knx-main",
            "source_type": "knx",
            "connection_json": {"gateway_ip": "127.0.0.1"},
            "acquisition_defaults_json": {
                "listen": True,
                "read_on_start": False,
                "periodic_interval_seconds": None,
            },
            "publish_defaults_json": {
                "enabled": True,
                "change_threshold": None,
            },
        },
    )
    stack.config_registry_json(
        "POST",
        f"/tenants/{tenant_id}/assets/asset-a/agents/agent-a"
        "/sources/knx-main/points",
        {
            "point_id": f"{tenant_id}|asset-a|knx-main|temperature",
            "point_key": "temperature",
            "point_ref": "2/0/0",
            "name": "Temperature",
            "value_type": "number",
            "value_model": "knx.dpt.9.001",
            "signal_type": "sensor",
            "acquisition_json": {"read_on_start": True},
            "publish_json": {"change_threshold": 1.0},
            "tags_json": {"room": "demo"},
        },
    )
