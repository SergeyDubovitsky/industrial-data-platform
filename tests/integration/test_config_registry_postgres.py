from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from idp_config_registry.application.use_cases.config_outbox import (
    MarkConfigOutboxPublished,
    ReleaseExpiredConfigOutboxLeases,
    ReserveConfigOutboxCommand,
    ReserveConfigOutboxRecords,
)
from idp_config_registry.application.use_cases.render_config import (
    RenderAgentRuntimeConfig,
    RenderAgentRuntimeConfigCommand,
    StoreRenderedAgentRuntimeConfig,
)
from idp_config_registry.domain.value_objects import ConfigOutboxStatus
from idp_config_registry.infrastructure.json_schema_validator import (
    JsonSchemaConfigPayloadValidator,
)
from idp_config_registry.infrastructure.postgres.unit_of_work import (
    PostgresUnitOfWorkFactory,
)
from idp_config_registry.main import create_app
from idp_config_registry.settings import ConfigRegistrySettings

pytestmark = pytest.mark.integration

CONTRACT_DIR = Path("docs/contracts/edge-telemetry-agent/schemas")


@pytest.mark.integration_smoke
def test_config_registry_persists_tenants_in_postgres(
    local_config_registry_postgres_stack,
) -> None:
    settings = ConfigRegistrySettings(
        database_url=local_config_registry_postgres_stack.database_url
    )

    with TestClient(create_app(settings=settings)) as client:
        create_response = client.post(
            "/tenants",
            json={"tenant_id": "tenant-a", "name": "Tenant A"},
        )
        duplicate_response = client.post(
            "/tenants",
            json={"tenant_id": "tenant-a", "name": "Tenant A"},
        )

    with TestClient(create_app(settings=settings)) as client:
        list_response = client.get("/tenants")

    assert create_response.status_code == 201
    assert duplicate_response.status_code == 409
    assert list_response.status_code == 200
    assert [tenant["tenant_id"] for tenant in list_response.json()] == ["tenant-a"]


def test_config_registry_persists_assets_in_postgres(
    local_config_registry_postgres_stack,
) -> None:
    settings = ConfigRegistrySettings(
        database_url=local_config_registry_postgres_stack.database_url
    )

    with TestClient(create_app(settings=settings)) as client:
        client.post(
            "/tenants",
            json={"tenant_id": "tenant-assets", "name": "Tenant Assets"},
        )
        create_response = client.post(
            "/tenants/tenant-assets/assets",
            json={
                "asset_id": "asset-a",
                "name": "Asset A",
                "description": "Primary monitored asset",
            },
        )
        duplicate_response = client.post(
            "/tenants/tenant-assets/assets",
            json={"asset_id": "asset-a", "name": "Asset A"},
        )

    with TestClient(create_app(settings=settings)) as client:
        list_response = client.get("/tenants/tenant-assets/assets")

    assert create_response.status_code == 201
    assert create_response.json()["asset_id"] == "asset-a"
    assert create_response.json()["description"] == "Primary monitored asset"
    assert duplicate_response.status_code == 409
    assert list_response.status_code == 200
    assert [asset["asset_id"] for asset in list_response.json()] == ["asset-a"]


def test_config_registry_persists_agents_in_postgres(
    local_config_registry_postgres_stack,
) -> None:
    settings = ConfigRegistrySettings(
        database_url=local_config_registry_postgres_stack.database_url
    )

    with TestClient(create_app(settings=settings)) as client:
        client.post(
            "/tenants",
            json={"tenant_id": "tenant-agents", "name": "Tenant Agents"},
        )
        client.post(
            "/tenants/tenant-agents/assets",
            json={"asset_id": "asset-a", "name": "Asset A"},
        )
        create_response = client.post(
            "/tenants/tenant-agents/assets/asset-a/agents",
            json={
                "agent_id": "agent-a",
                "name": "Agent A",
                "bootstrap_hint_json": {"mqtt_profile": "local"},
            },
        )
        duplicate_response = client.post(
            "/tenants/tenant-agents/assets/asset-a/agents",
            json={"agent_id": "agent-a"},
        )

    with TestClient(create_app(settings=settings)) as client:
        list_response = client.get("/tenants/tenant-agents/assets/asset-a/agents")

    assert create_response.status_code == 201
    assert create_response.json()["agent_id"] == "agent-a"
    assert create_response.json()["bootstrap_hint_json"] == {"mqtt_profile": "local"}
    assert duplicate_response.status_code == 409
    assert list_response.status_code == 200
    assert [agent["agent_id"] for agent in list_response.json()] == ["agent-a"]


def test_config_registry_persists_sources_in_postgres(
    local_config_registry_postgres_stack,
) -> None:
    settings = ConfigRegistrySettings(
        database_url=local_config_registry_postgres_stack.database_url
    )

    with TestClient(create_app(settings=settings)) as client:
        client.post(
            "/tenants",
            json={"tenant_id": "tenant-sources", "name": "Tenant Sources"},
        )
        client.post(
            "/tenants/tenant-sources/assets",
            json={"asset_id": "asset-a", "name": "Asset A"},
        )
        client.post(
            "/tenants/tenant-sources/assets/asset-a/agents",
            json={"agent_id": "agent-a"},
        )
        create_response = client.post(
            "/tenants/tenant-sources/assets/asset-a/agents/agent-a/sources",
            json={
                "source_id": "knx-main",
                "source_type": "knx",
                "connection_json": {"gateway": "127.0.0.1"},
            },
        )
        duplicate_response = client.post(
            "/tenants/tenant-sources/assets/asset-a/agents/agent-a/sources",
            json={"source_id": "knx-main", "source_type": "knx"},
        )

    with TestClient(create_app(settings=settings)) as client:
        list_response = client.get(
            "/tenants/tenant-sources/assets/asset-a/agents/agent-a/sources"
        )

    assert create_response.status_code == 201
    assert create_response.json()["source_id"] == "knx-main"
    assert create_response.json()["connection_json"] == {"gateway": "127.0.0.1"}
    assert duplicate_response.status_code == 409
    assert list_response.status_code == 200
    assert [source["source_id"] for source in list_response.json()] == ["knx-main"]


def test_config_registry_persists_points_in_postgres(
    local_config_registry_postgres_stack,
) -> None:
    settings = ConfigRegistrySettings(
        database_url=local_config_registry_postgres_stack.database_url
    )

    with TestClient(create_app(settings=settings)) as client:
        client.post(
            "/tenants",
            json={"tenant_id": "tenant-points", "name": "Tenant Points"},
        )
        client.post(
            "/tenants/tenant-points/assets",
            json={"asset_id": "asset-a", "name": "Asset A"},
        )
        client.post(
            "/tenants/tenant-points/assets/asset-a/agents",
            json={"agent_id": "agent-a"},
        )
        client.post(
            "/tenants/tenant-points/assets/asset-a/agents/agent-a/sources",
            json={"source_id": "knx-main", "source_type": "knx"},
        )
        create_response = client.post(
            "/tenants/tenant-points/assets/asset-a/agents/agent-a"
            "/sources/knx-main/points",
            json={
                "point_id": "tenant-points|asset-a|knx-main|lights.main",
                "point_key": "lights.main",
                "point_ref": "1/1/1",
                "name": "Main Light",
                "value_type": "boolean",
                "value_model": "1.001",
                "signal_type": "feedback",
                "tags_json": {"room": "hall"},
            },
        )
        duplicate_response = client.post(
            "/tenants/tenant-points/assets/asset-a/agents/agent-a"
            "/sources/knx-main/points",
            json={
                "point_id": "tenant-points|asset-a|knx-main|lights.main",
                "point_key": "lights.secondary",
                "point_ref": "1/1/2",
                "name": "Secondary Light",
                "value_type": "boolean",
                "value_model": "1.001",
                "signal_type": "feedback",
            },
        )

    with TestClient(create_app(settings=settings)) as client:
        list_response = client.get(
            "/tenants/tenant-points/assets/asset-a/agents/agent-a"
            "/sources/knx-main/points"
        )

    assert create_response.status_code == 201
    assert create_response.json()["point_key"] == "lights.main"
    assert create_response.json()["tags_json"] == {"room": "hall"}
    assert duplicate_response.status_code == 409
    assert list_response.status_code == 200
    assert [point["point_key"] for point in list_response.json()] == ["lights.main"]


@pytest.mark.asyncio
async def test_config_registry_persists_and_reserves_outbox_records_in_postgres(
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
        rendered = await RenderAgentRuntimeConfig(
            unit_of_work_factory(),
            validator,
        ).execute(
            RenderAgentRuntimeConfigCommand(
                tenant_id="tenant-outbox",
                asset_id="asset-a",
                agent_id="agent-a",
                config_revision="rev-outbox-001",
                issued_at=datetime(2026, 5, 3, 10, 0, tzinfo=UTC),
                source_config_revisions={"knx-main": "rev-outbox-001-knx-main"},
            )
        )
        await StoreRenderedAgentRuntimeConfig(unit_of_work_factory(), validator).execute(
            rendered
        )

        now = datetime.now(tz=UTC) + timedelta(seconds=1)
        reserved = await ReserveConfigOutboxRecords(unit_of_work_factory()).execute(
            ReserveConfigOutboxCommand(
                limit=10,
                now=now,
                lease_duration=timedelta(seconds=30),
            )
        )
        published = await MarkConfigOutboxPublished(
            unit_of_work_factory()
        ).execute(reserved[0].outbox_id, now=now + timedelta(seconds=5))
        released = await ReleaseExpiredConfigOutboxLeases(
            unit_of_work_factory()
        ).execute(now=now + timedelta(seconds=31))
    finally:
        await unit_of_work_factory.dispose()

    assert [record.config_scope for record in reserved] == [
        "agent_runtime",
        "source:knx-main",
    ]
    assert all(record.status == ConfigOutboxStatus.INFLIGHT for record in reserved)
    assert published is not None
    assert published.status == ConfigOutboxStatus.PUBLISHED
    assert released == 1


def _create_renderable_agent_graph(client: TestClient) -> None:
    client.post(
        "/tenants",
        json={"tenant_id": "tenant-outbox", "name": "Tenant Outbox"},
    )
    client.post(
        "/tenants/tenant-outbox/assets",
        json={"asset_id": "asset-a", "name": "Asset A"},
    )
    client.post(
        "/tenants/tenant-outbox/assets/asset-a/agents",
        json={"agent_id": "agent-a"},
    )
    client.post(
        "/tenants/tenant-outbox/assets/asset-a/agents/agent-a/sources",
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
        "/tenants/tenant-outbox/assets/asset-a/agents/agent-a"
        "/sources/knx-main/points",
        json={
            "point_id": "tenant-outbox|asset-a|knx-main|temperature",
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
