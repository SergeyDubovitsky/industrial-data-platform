from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from idp_config_registry.application.errors import (
    AgentNotFoundError,
    ConfigPayloadValidationError,
    ConfigRenderError,
    DuplicateConfigRevisionError,
)
from idp_config_registry.application.use_cases.agents import (
    CreateAgent,
    CreateAgentCommand,
)
from idp_config_registry.application.use_cases.assets import (
    CreateAsset,
    CreateAssetCommand,
)
from idp_config_registry.application.use_cases.points import (
    CreatePoint,
    CreatePointCommand,
)
from idp_config_registry.application.use_cases.render_config import (
    RenderAgentRuntimeConfig,
    RenderAgentRuntimeConfigCommand,
    StoreRenderedAgentRuntimeConfig,
)
from idp_config_registry.application.use_cases.sources import (
    CreateSource,
    CreateSourceCommand,
)
from idp_config_registry.application.use_cases.tenants import (
    CreateTenant,
    CreateTenantCommand,
)
from idp_config_registry.domain.value_objects import SignalType, ValueType
from idp_config_registry.infrastructure.json_schema_validator import (
    JsonSchemaConfigPayloadValidator,
)
from idp_config_registry.infrastructure.memory.unit_of_work import (
    InMemoryUnitOfWorkFactory,
)

pytestmark = pytest.mark.asyncio

CONTRACT_DIR = Path("docs/contracts/edge-telemetry-agent/schemas")


async def test_render_agent_config_builds_valid_runtime_and_source_payloads() -> None:
    unit_of_work_factory = InMemoryUnitOfWorkFactory()
    await _create_registry_graph(unit_of_work_factory)

    rendered = await RenderAgentRuntimeConfig(
        unit_of_work_factory(),
        JsonSchemaConfigPayloadValidator.from_contract_dir(CONTRACT_DIR),
    ).execute(
        RenderAgentRuntimeConfigCommand(
            tenant_id="tenant-a",
            asset_id="asset-a",
            agent_id="agent-a",
            config_revision="rev-2026-05-03-001",
            issued_at=datetime(2026, 5, 3, 10, 15, 0, tzinfo=UTC),
            source_config_revisions={"knx-main": "rev-2026-05-03-001-knx-main"},
        )
    )

    assert rendered.agent_runtime_payload == {
        "message_type": "idp.edge.agent-runtime-config.v1",
        "tenant_id": "tenant-a",
        "asset_id": "asset-a",
        "agent_id": "agent-a",
        "config_revision": "rev-2026-05-03-001",
        "issued_at": "2026-05-03T10:15:00Z",
        "sources": [
            {
                "source_id": "knx-main",
                "source_config_revision": "rev-2026-05-03-001-knx-main",
                "enabled": True,
            }
        ],
    }
    assert len(rendered.source_payloads) == 1

    source_payload = rendered.source_payloads[0].payload
    assert source_payload["message_type"] == "idp.edge.source-config.v1"
    assert source_payload["source_id"] == "knx-main"
    assert source_payload["source_config_revision"] == (
        "rev-2026-05-03-001-knx-main"
    )
    assert source_payload["connection"] == {"gateway_ip": "127.0.0.1"}
    assert [point["point_key"] for point in source_payload["points"]] == [
        "temperature"
    ]
    assert source_payload["points"][0]["acquisition"] == {
        "listen": True,
        "read_on_start": True,
        "periodic_interval_seconds": None,
    }
    assert source_payload["points"][0]["publish"] == {
        "enabled": True,
        "change_threshold": 1.0,
    }


async def test_render_agent_config_rejects_missing_agent() -> None:
    unit_of_work_factory = InMemoryUnitOfWorkFactory()

    with pytest.raises(AgentNotFoundError):
        await RenderAgentRuntimeConfig(
            unit_of_work_factory(),
            JsonSchemaConfigPayloadValidator.from_contract_dir(CONTRACT_DIR),
        ).execute(
            RenderAgentRuntimeConfigCommand(
                tenant_id="tenant-a",
                asset_id="asset-a",
                agent_id="agent-a",
                config_revision="rev-2026-05-03-001",
                issued_at=datetime(2026, 5, 3, tzinfo=UTC),
            )
        )


async def test_render_agent_config_rejects_missing_source_revision() -> None:
    unit_of_work_factory = InMemoryUnitOfWorkFactory()
    await _create_registry_graph(unit_of_work_factory)

    with pytest.raises(ConfigRenderError, match="source_config_revision"):
        await RenderAgentRuntimeConfig(
            unit_of_work_factory(),
            JsonSchemaConfigPayloadValidator.from_contract_dir(CONTRACT_DIR),
        ).execute(
            RenderAgentRuntimeConfigCommand(
                tenant_id="tenant-a",
                asset_id="asset-a",
                agent_id="agent-a",
                config_revision="rev-2026-05-03-001",
                issued_at=datetime(2026, 5, 3, tzinfo=UTC),
                source_config_revisions={},
            )
        )


async def test_render_agent_config_rejects_contract_invalid_source_payload() -> None:
    unit_of_work_factory = InMemoryUnitOfWorkFactory()
    await _create_registry_graph(
        unit_of_work_factory,
        publish_defaults={"enabled": "not-a-bool"},
    )

    with pytest.raises(ConfigPayloadValidationError, match="enabled"):
        await RenderAgentRuntimeConfig(
            unit_of_work_factory(),
            JsonSchemaConfigPayloadValidator.from_contract_dir(CONTRACT_DIR),
        ).execute(
            RenderAgentRuntimeConfigCommand(
                tenant_id="tenant-a",
                asset_id="asset-a",
                agent_id="agent-a",
                config_revision="rev-2026-05-03-001",
                issued_at=datetime(2026, 5, 3, tzinfo=UTC),
            )
        )


async def test_render_agent_config_backfills_missing_source_and_point_settings() -> None:
    unit_of_work_factory = InMemoryUnitOfWorkFactory()
    await _create_registry_graph(
        unit_of_work_factory,
        acquisition_defaults={},
        publish_defaults={},
        point_acquisition={},
        point_publish={},
    )

    rendered = await RenderAgentRuntimeConfig(
        unit_of_work_factory(),
        JsonSchemaConfigPayloadValidator.from_contract_dir(CONTRACT_DIR),
    ).execute(
        RenderAgentRuntimeConfigCommand(
            tenant_id="tenant-a",
            asset_id="asset-a",
            agent_id="agent-a",
            config_revision="rev-2026-05-03-legacy",
            issued_at=datetime(2026, 5, 3, 10, 15, 0, tzinfo=UTC),
            source_config_revisions={"knx-main": "rev-2026-05-03-legacy-knx-main"},
        )
    )

    source_payload = rendered.source_payloads[0].payload
    assert source_payload["acquisition_defaults"] == {
        "listen": True,
        "read_on_start": False,
        "periodic_interval_seconds": None,
    }
    assert source_payload["publish_defaults"] == {
        "enabled": True,
        "change_threshold": None,
    }
    assert source_payload["points"][0]["acquisition"] == {
        "listen": True,
        "read_on_start": False,
        "periodic_interval_seconds": None,
    }
    assert source_payload["points"][0]["publish"] == {
        "enabled": True,
        "change_threshold": None,
    }


async def test_render_agent_config_suppresses_command_point_publish() -> None:
    unit_of_work_factory = InMemoryUnitOfWorkFactory()
    await _create_registry_graph(unit_of_work_factory)
    await CreatePoint(unit_of_work_factory()).execute(
        CreatePointCommand(
            tenant_id="tenant-a",
            asset_id="asset-a",
            agent_id="agent-a",
            source_id="knx-main",
            point_id="tenant-a|asset-a|knx-main|switch-command",
            point_key="switch-command",
            point_ref="0/0/1",
            name="Switch Command",
            value_type=ValueType.BOOLEAN,
            value_model="knx.dpt.1.001",
            signal_type=SignalType.COMMAND,
            publish_json={"enabled": True},
        )
    )

    rendered = await RenderAgentRuntimeConfig(
        unit_of_work_factory(),
        JsonSchemaConfigPayloadValidator.from_contract_dir(CONTRACT_DIR),
    ).execute(
        RenderAgentRuntimeConfigCommand(
            tenant_id="tenant-a",
            asset_id="asset-a",
            agent_id="agent-a",
            config_revision="rev-2026-05-03-001",
            issued_at=datetime(2026, 5, 3, 10, 15, 0, tzinfo=UTC),
            source_config_revisions={"knx-main": "rev-2026-05-03-001-knx-main"},
        )
    )

    points_by_key = {
        point["point_key"]: point
        for point in rendered.source_payloads[0].payload["points"]
    }
    assert points_by_key["switch-command"]["signal_type"] == "command"
    assert points_by_key["switch-command"]["publish"] == {
        "enabled": False,
        "change_threshold": None,
    }


async def test_store_rendered_agent_config_persists_runtime_and_source_revisions() -> None:
    unit_of_work_factory = InMemoryUnitOfWorkFactory()
    await _create_registry_graph(unit_of_work_factory)
    validator = JsonSchemaConfigPayloadValidator.from_contract_dir(CONTRACT_DIR)
    rendered = await RenderAgentRuntimeConfig(unit_of_work_factory(), validator).execute(
        RenderAgentRuntimeConfigCommand(
            tenant_id="tenant-a",
            asset_id="asset-a",
            agent_id="agent-a",
            config_revision="rev-2026-05-03-001",
            issued_at=datetime(2026, 5, 3, 10, 15, 0, tzinfo=UTC),
            source_config_revisions={"knx-main": "rev-2026-05-03-001-knx-main"},
        )
    )

    runtime_revision = await StoreRenderedAgentRuntimeConfig(
        unit_of_work_factory(),
        validator,
    ).execute(rendered)
    async with unit_of_work_factory() as unit_of_work:
        stored_runtime = await unit_of_work.agent_runtime_config_revisions.get(
            "tenant-a",
            "asset-a",
            "agent-a",
            "rev-2026-05-03-001",
        )
        stored_sources = (
            await unit_of_work.source_config_revisions.list_for_runtime_revision(
                "tenant-a",
                "asset-a",
                "agent-a",
                "rev-2026-05-03-001",
            )
        )
        outbox_records = await unit_of_work.config_outbox.list_for_config_revision(
            "tenant-a",
            "asset-a",
            "agent-a",
            "rev-2026-05-03-001",
        )

    assert runtime_revision.config_revision == "rev-2026-05-03-001"
    assert stored_runtime is not None
    assert stored_runtime.agent_runtime_payload_json == rendered.agent_runtime_payload
    assert [revision.source_id for revision in stored_sources] == ["knx-main"]
    assert stored_sources[0].source_payload_json == rendered.source_payloads[0].payload
    assert [record.config_scope for record in outbox_records] == [
        "agent_runtime",
        "source:knx-main",
    ]
    assert outbox_records[0].payload_json["target_mqtt_topic"] == (
        "idp/v1/agents/agent-a/config/agent-runtime"
    )
    assert outbox_records[1].payload_json["target_mqtt_topic"] == (
        "idp/v1/agents/agent-a/sources/knx-main/config"
    )


async def test_store_rendered_agent_config_rejects_duplicate_revision() -> None:
    unit_of_work_factory = InMemoryUnitOfWorkFactory()
    await _create_registry_graph(unit_of_work_factory)
    validator = JsonSchemaConfigPayloadValidator.from_contract_dir(CONTRACT_DIR)
    rendered = await RenderAgentRuntimeConfig(unit_of_work_factory(), validator).execute(
        RenderAgentRuntimeConfigCommand(
            tenant_id="tenant-a",
            asset_id="asset-a",
            agent_id="agent-a",
            config_revision="rev-2026-05-03-001",
            issued_at=datetime(2026, 5, 3, 10, 15, 0, tzinfo=UTC),
        )
    )

    await StoreRenderedAgentRuntimeConfig(unit_of_work_factory(), validator).execute(rendered)
    with pytest.raises(DuplicateConfigRevisionError):
        await StoreRenderedAgentRuntimeConfig(
            unit_of_work_factory(),
            validator,
        ).execute(rendered)


async def test_store_rendered_agent_config_rejects_invalid_delivery_payload() -> None:
    unit_of_work_factory = InMemoryUnitOfWorkFactory()
    await _create_registry_graph(unit_of_work_factory)
    validator = JsonSchemaConfigPayloadValidator.from_contract_dir(CONTRACT_DIR)
    rendered = await RenderAgentRuntimeConfig(unit_of_work_factory(), validator).execute(
        RenderAgentRuntimeConfigCommand(
            tenant_id="tenant-a",
            asset_id="asset-a",
            agent_id="agent-a",
            config_revision="rev-2026-05-03-001",
            issued_at=datetime(2026, 5, 3, 10, 15, 0, tzinfo=UTC),
        )
    )

    with pytest.raises(ConfigPayloadValidationError, match="delivery rejected"):
        await StoreRenderedAgentRuntimeConfig(
            unit_of_work_factory(),
            RejectDeliveryValidator(),
        ).execute(rendered)
    async with unit_of_work_factory() as unit_of_work:
        stored_runtime = await unit_of_work.agent_runtime_config_revisions.get(
            "tenant-a",
            "asset-a",
            "agent-a",
            "rev-2026-05-03-001",
        )
        outbox_records = await unit_of_work.config_outbox.list_for_config_revision(
            "tenant-a",
            "asset-a",
            "agent-a",
            "rev-2026-05-03-001",
        )

    assert stored_runtime is None
    assert outbox_records == []


async def test_json_schema_validator_rejects_invalid_config_delivery_payload() -> None:
    validator = JsonSchemaConfigPayloadValidator.from_contract_dir(CONTRACT_DIR)

    with pytest.raises(ConfigPayloadValidationError, match="config_scope"):
        validator.validate_config_delivery(
            {
                "message_type": "idp.edge.config.delivery.v1",
                "tenant_id": "tenant-a",
                "asset_id": "asset-a",
                "agent_id": "agent-a",
                "config_revision": "rev-001",
                "config_scope": "not-a-valid-scope",
                "target_mqtt_topic": "idp/v1/agents/agent-a/config/agent-runtime",
                "mqtt_retain": True,
                "mqtt_qos": 1,
                "operation": "upsert",
                "payload_message_type": "idp.edge.agent-runtime-config.v1",
                "payload": {},
                "idempotency_key": "tenant-a|asset-a|agent-a|rev-001|agent_runtime",
                "issued_at": "2026-05-03T10:00:00Z",
            }
        )


class RejectDeliveryValidator:
    def validate_agent_runtime_config(self, payload: dict[str, Any]) -> None:
        return None

    def validate_source_config(self, payload: dict[str, Any]) -> None:
        return None

    def validate_config_delivery(self, payload: dict[str, Any]) -> None:
        raise ConfigPayloadValidationError(
            "idp.edge.config.delivery.v1",
            ["delivery rejected"],
        )


async def _create_registry_graph(
    unit_of_work_factory: InMemoryUnitOfWorkFactory,
    *,
    acquisition_defaults: dict[str, object] | None = None,
    publish_defaults: dict[str, object] | None = None,
    point_acquisition: dict[str, object] | None = None,
    point_publish: dict[str, object] | None = None,
) -> None:
    await CreateTenant(unit_of_work_factory()).execute(
        CreateTenantCommand(tenant_id="tenant-a", name="Tenant A")
    )
    await CreateAsset(unit_of_work_factory()).execute(
        CreateAssetCommand(
            tenant_id="tenant-a",
            asset_id="asset-a",
            name="Asset A",
        )
    )
    await CreateAgent(unit_of_work_factory()).execute(
        CreateAgentCommand(
            tenant_id="tenant-a",
            asset_id="asset-a",
            agent_id="agent-a",
        )
    )
    await CreateSource(unit_of_work_factory()).execute(
        CreateSourceCommand(
            tenant_id="tenant-a",
            asset_id="asset-a",
            agent_id="agent-a",
            source_id="knx-main",
            source_type="knx",
            connection_json={"gateway_ip": "127.0.0.1"},
            acquisition_defaults_json=(
                dict(acquisition_defaults)
                if acquisition_defaults is not None
                else {
                    "listen": True,
                    "read_on_start": False,
                    "periodic_interval_seconds": None,
                }
            ),
            publish_defaults_json=(
                dict(publish_defaults)
                if publish_defaults is not None
                else {
                    "enabled": True,
                    "change_threshold": None,
                }
            ),
        )
    )
    await CreatePoint(unit_of_work_factory()).execute(
        CreatePointCommand(
            tenant_id="tenant-a",
            asset_id="asset-a",
            agent_id="agent-a",
            source_id="knx-main",
            point_id="tenant-a|asset-a|knx-main|temperature",
            point_key="temperature",
            point_ref="2/0/0",
            name="Temperature",
            value_type=ValueType.NUMBER,
            value_model="knx.dpt.9.001",
            signal_type=SignalType.SENSOR,
            unit="C",
            acquisition_json=(
                dict(point_acquisition)
                if point_acquisition is not None
                else {"read_on_start": True}
            ),
            publish_json=(
                dict(point_publish)
                if point_publish is not None
                else {"change_threshold": 1.0}
            ),
            tags_json={"room": "demo"},
        )
    )
    await CreatePoint(unit_of_work_factory()).execute(
        CreatePointCommand(
            tenant_id="tenant-a",
            asset_id="asset-a",
            agent_id="agent-a",
            source_id="knx-main",
            point_id="tenant-a|asset-a|knx-main|disabled",
            point_key="disabled",
            point_ref="2/0/1",
            name="Disabled",
            value_type=ValueType.BOOLEAN,
            value_model="knx.dpt.1.001",
            signal_type=SignalType.FEEDBACK,
            enabled=False,
        )
    )
