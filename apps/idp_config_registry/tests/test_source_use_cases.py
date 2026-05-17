from __future__ import annotations

import pytest

from idp_config_registry.application.errors import (
    AgentNotFoundError,
    DuplicateSourceError,
)
from idp_config_registry.application.use_cases.agents import (
    CreateAgent,
    CreateAgentCommand,
)
from idp_config_registry.application.use_cases.assets import (
    CreateAsset,
    CreateAssetCommand,
)
from idp_config_registry.application.use_cases.sources import (
    CreateSource,
    CreateSourceCommand,
    ListSources,
)
from idp_config_registry.application.use_cases.tenants import (
    CreateTenant,
    CreateTenantCommand,
)
from idp_config_registry.domain.value_objects import DomainValidationError
from idp_config_registry.infrastructure.memory.unit_of_work import (
    InMemoryUnitOfWorkFactory,
)

pytestmark = pytest.mark.asyncio


async def _create_tenant_asset_and_agent(
    unit_of_work_factory: InMemoryUnitOfWorkFactory,
) -> None:
    await CreateTenant(unit_of_work_factory()).execute(
        CreateTenantCommand(tenant_code="tenant-a", name="Tenant A")
    )
    await CreateAsset(unit_of_work_factory()).execute(
        CreateAssetCommand(
            tenant_code="tenant-a",
            asset_code="asset-a",
            name="Asset A",
        )
    )
    await CreateAgent(unit_of_work_factory()).execute(
        CreateAgentCommand(
            tenant_code="tenant-a",
            asset_code="asset-a",
            agent_code="agent-a",
        )
    )


async def test_create_source_persists_entity_under_existing_agent() -> None:
    unit_of_work_factory = InMemoryUnitOfWorkFactory()
    await _create_tenant_asset_and_agent(unit_of_work_factory)

    source = await CreateSource(unit_of_work_factory()).execute(
        CreateSourceCommand(
            tenant_code="tenant-a",
            asset_code="asset-a",
            agent_code="agent-a",
            source_code="knx-main",
            source_type="knx",
            name="Main KNX Line",
            connection_json={"gateway": "127.0.0.1"},
        )
    )
    sources = await ListSources(unit_of_work_factory()).execute(
        "tenant-a",
        "asset-a",
        "agent-a",
    )

    assert source.source_code == "knx-main"
    assert source.connection_json == {"gateway": "127.0.0.1"}
    assert sources == [source]


async def test_create_source_rejects_missing_agent() -> None:
    unit_of_work_factory = InMemoryUnitOfWorkFactory()

    with pytest.raises(AgentNotFoundError):
        await CreateSource(unit_of_work_factory()).execute(
            CreateSourceCommand(
                tenant_code="tenant-a",
                asset_code="asset-a",
                agent_code="agent-a",
                source_code="knx-main",
                source_type="knx",
            )
        )


async def test_create_source_rejects_duplicate_source_id_in_agent() -> None:
    unit_of_work_factory = InMemoryUnitOfWorkFactory()
    await _create_tenant_asset_and_agent(unit_of_work_factory)
    command = CreateSourceCommand(
        tenant_code="tenant-a",
        asset_code="asset-a",
        agent_code="agent-a",
        source_code="knx-main",
        source_type="knx",
    )

    await CreateSource(unit_of_work_factory()).execute(command)
    with pytest.raises(DuplicateSourceError):
        await CreateSource(unit_of_work_factory()).execute(command)


async def test_create_source_rejects_invalid_source_id() -> None:
    unit_of_work_factory = InMemoryUnitOfWorkFactory()
    await _create_tenant_asset_and_agent(unit_of_work_factory)

    with pytest.raises(DomainValidationError):
        await CreateSource(unit_of_work_factory()).execute(
            CreateSourceCommand(
                tenant_code="tenant-a",
                asset_code="asset-a",
                agent_code="agent-a",
                source_code="KNX Main",
                source_type="knx",
            )
        )


async def test_list_sources_rejects_missing_agent() -> None:
    unit_of_work_factory = InMemoryUnitOfWorkFactory()

    with pytest.raises(AgentNotFoundError):
        await ListSources(unit_of_work_factory()).execute(
            "tenant-a",
            "asset-a",
            "agent-a",
        )
