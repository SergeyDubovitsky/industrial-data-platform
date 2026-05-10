from __future__ import annotations

import pytest

from idp_config_registry.application.errors import (
    DuplicatePointError,
    SourceNotFoundError,
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
    ListPoints,
)
from idp_config_registry.application.use_cases.sources import (
    CreateSource,
    CreateSourceCommand,
)
from idp_config_registry.application.use_cases.tenants import (
    CreateTenant,
    CreateTenantCommand,
)
from idp_config_registry.domain.value_objects import (
    DomainValidationError,
    SignalType,
    ValueType,
)
from idp_config_registry.infrastructure.memory.unit_of_work import (
    InMemoryUnitOfWorkFactory,
)

pytestmark = pytest.mark.asyncio


async def _create_tenant_asset_agent_and_source(
    unit_of_work_factory: InMemoryUnitOfWorkFactory,
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
        )
    )


def _point_command(
    *,
    point_id: str = "tenant-a|asset-a|knx-main|lights.main",
    point_key: str = "lights.main",
    point_ref: str = "1/1/1",
) -> CreatePointCommand:
    return CreatePointCommand(
        tenant_id="tenant-a",
        asset_id="asset-a",
        agent_id="agent-a",
        source_id="knx-main",
        point_id=point_id,
        point_key=point_key,
        point_ref=point_ref,
        name="Main Light",
        value_type=ValueType.BOOLEAN,
        value_model="1.001",
        signal_type=SignalType.FEEDBACK,
        tags_json={"room": "hall"},
    )


async def test_create_point_persists_entity_under_existing_source() -> None:
    unit_of_work_factory = InMemoryUnitOfWorkFactory()
    await _create_tenant_asset_agent_and_source(unit_of_work_factory)

    point = await CreatePoint(unit_of_work_factory()).execute(_point_command())
    points = await ListPoints(unit_of_work_factory()).execute(
        "tenant-a",
        "asset-a",
        "agent-a",
        "knx-main",
    )

    assert point.point_key == "lights.main"
    assert point.tags_json == {"room": "hall"}
    assert points == [point]


async def test_create_point_rejects_missing_source() -> None:
    unit_of_work_factory = InMemoryUnitOfWorkFactory()

    with pytest.raises(SourceNotFoundError):
        await CreatePoint(unit_of_work_factory()).execute(_point_command())


async def test_create_point_rejects_duplicate_point_id_in_tenant() -> None:
    unit_of_work_factory = InMemoryUnitOfWorkFactory()
    await _create_tenant_asset_agent_and_source(unit_of_work_factory)

    await CreatePoint(unit_of_work_factory()).execute(_point_command())
    with pytest.raises(DuplicatePointError):
        await CreatePoint(unit_of_work_factory()).execute(
            _point_command(point_key="lights.secondary", point_ref="1/1/2")
        )


async def test_create_point_rejects_duplicate_point_key_in_source() -> None:
    unit_of_work_factory = InMemoryUnitOfWorkFactory()
    await _create_tenant_asset_agent_and_source(unit_of_work_factory)

    await CreatePoint(unit_of_work_factory()).execute(_point_command())
    with pytest.raises(DuplicatePointError):
        await CreatePoint(unit_of_work_factory()).execute(
            _point_command(
                point_id="tenant-a|asset-a|knx-main|lights.secondary",
                point_ref="1/1/2",
            )
        )


async def test_create_point_rejects_duplicate_point_ref_in_source() -> None:
    unit_of_work_factory = InMemoryUnitOfWorkFactory()
    await _create_tenant_asset_agent_and_source(unit_of_work_factory)

    await CreatePoint(unit_of_work_factory()).execute(_point_command())
    with pytest.raises(DuplicatePointError):
        await CreatePoint(unit_of_work_factory()).execute(
            _point_command(
                point_id="tenant-a|asset-a|knx-main|lights.secondary",
                point_key="lights.secondary",
            )
        )


async def test_create_point_rejects_invalid_point_key() -> None:
    unit_of_work_factory = InMemoryUnitOfWorkFactory()
    await _create_tenant_asset_agent_and_source(unit_of_work_factory)

    with pytest.raises(DomainValidationError):
        await CreatePoint(unit_of_work_factory()).execute(
            _point_command(point_key="lights main")
        )


async def test_list_points_rejects_missing_source() -> None:
    unit_of_work_factory = InMemoryUnitOfWorkFactory()

    with pytest.raises(SourceNotFoundError):
        await ListPoints(unit_of_work_factory()).execute(
            "tenant-a",
            "asset-a",
            "agent-a",
            "knx-main",
        )
