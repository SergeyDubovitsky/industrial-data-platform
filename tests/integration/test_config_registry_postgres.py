from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

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
from idp_config_registry.infrastructure.postgres.database import create_engine
from idp_config_registry.infrastructure.postgres.unit_of_work import (
    PostgresUnitOfWorkFactory,
)
from idp_config_registry.main import create_app
from idp_config_registry.settings import ConfigRegistrySettings

pytestmark = pytest.mark.integration

CONTRACT_DIR = Path("docs/contracts/edge-telemetry-agent/schemas")


@pytest.mark.asyncio
async def test_config_registry_postgres_schema_uses_internal_uuid_keys(
    local_config_registry_postgres_stack,
) -> None:
    engine = create_engine(local_config_registry_postgres_stack.database_url)
    try:
        async with engine.connect() as connection:
            columns = {
                table: await _load_column_types(connection, table)
                for table in (
                    "tenants",
                    "assets",
                    "agents",
                    "sources",
                    "points",
                )
            }
            primary_keys = {
                table: await _load_primary_key_columns(connection, table)
                for table in columns
            }
            foreign_keys = await _load_foreign_key_edges(
                connection,
                (
                    "assets",
                    "agents",
                    "sources",
                    "points",
                ),
            )
    finally:
        await engine.dispose()

    expected_code_columns = {
        "tenants": "tenant_code",
        "assets": "asset_code",
        "agents": "agent_code",
        "sources": "source_code",
        "points": "point_code",
    }

    for table, table_columns in columns.items():
        assert table_columns["id"] == "uuid"
        assert primary_keys[table] == ("id",)
        assert table_columns[expected_code_columns[table]] == "text"
        assert "code" not in table_columns

    assert "tenant_id" not in columns["tenants"]
    assert "asset_id" not in columns["assets"]
    assert "agent_id" not in columns["agents"]
    assert "source_id" not in columns["sources"]
    assert "point_id" not in columns["points"]

    assert columns["assets"]["tenant_id"] == "uuid"
    assert columns["agents"]["tenant_id"] == "uuid"
    assert columns["agents"]["asset_id"] == "uuid"
    assert columns["sources"]["tenant_id"] == "uuid"
    assert columns["sources"]["agent_id"] == "uuid"
    assert columns["points"]["tenant_id"] == "uuid"
    assert columns["points"]["source_id"] == "uuid"

    assert ("assets", "tenant_id", "tenants", "id") in foreign_keys
    assert ("agents", "tenant_id", "tenants", "id") in foreign_keys
    assert ("agents", "asset_id", "assets", "id") in foreign_keys
    assert ("sources", "tenant_id", "tenants", "id") in foreign_keys
    assert ("sources", "agent_id", "agents", "id") in foreign_keys
    assert ("points", "tenant_id", "tenants", "id") in foreign_keys
    assert ("points", "source_id", "sources", "id") in foreign_keys


async def _load_column_types(connection: object, table_name: str) -> dict[str, str]:
    result = await connection.execute(
        text(
            """
            select
                a.attname as column_name,
                pg_catalog.format_type(a.atttypid, a.atttypmod) as data_type
            from pg_catalog.pg_attribute a
            join pg_catalog.pg_class c on c.oid = a.attrelid
            join pg_catalog.pg_namespace n on n.oid = c.relnamespace
            where n.nspname = 'public'
              and c.relname = :table_name
              and a.attnum > 0
              and not a.attisdropped
            order by a.attnum
            """
        ),
        {"table_name": table_name},
    )
    return {str(row.column_name): str(row.data_type) for row in result}


async def _load_primary_key_columns(
    connection: object,
    table_name: str,
) -> tuple[str, ...]:
    result = await connection.execute(
        text(
            """
            select a.attname as column_name
            from pg_catalog.pg_constraint con
            join pg_catalog.pg_class c on c.oid = con.conrelid
            join pg_catalog.pg_namespace n on n.oid = c.relnamespace
            join unnest(con.conkey) with ordinality key(attnum, ord)
                on true
            join pg_catalog.pg_attribute a
                on a.attrelid = con.conrelid
               and a.attnum = key.attnum
            where n.nspname = 'public'
              and c.relname = :table_name
              and con.contype = 'p'
            order by key.ord
            """
        ),
        {"table_name": table_name},
    )
    return tuple(str(row.column_name) for row in result)


async def _load_foreign_key_edges(
    connection: object,
    table_names: tuple[str, ...],
) -> set[tuple[str, str, str, str]]:
    result = await connection.execute(
        text(
            """
            select
                source_table.relname as source_table,
                source_column.attname as source_column,
                target_table.relname as target_table,
                target_column.attname as target_column
            from pg_catalog.pg_constraint con
            join pg_catalog.pg_class source_table on source_table.oid = con.conrelid
            join pg_catalog.pg_class target_table on target_table.oid = con.confrelid
            join unnest(con.conkey, con.confkey) as key(source_attnum, target_attnum)
                on true
            join pg_catalog.pg_attribute source_column
                on source_column.attrelid = con.conrelid
               and source_column.attnum = key.source_attnum
            join pg_catalog.pg_attribute target_column
                on target_column.attrelid = con.confrelid
               and target_column.attnum = key.target_attnum
            where con.contype = 'f'
              and source_table.relname = any(:table_names)
            """
        ),
        {"table_names": list(table_names)},
    )
    return {
        (
            str(row.source_table),
            str(row.source_column),
            str(row.target_table),
            str(row.target_column),
        )
        for row in result
    }


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
                tenant_code="tenant-outbox",
                asset_code="asset-a",
                agent_code="agent-a",
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
