from __future__ import annotations

import pytest

from idp_config_registry.application.errors import (
    AssetNotFoundError,
    DuplicateAgentError,
)
from idp_config_registry.application.use_cases.agents import (
    CreateAgent,
    CreateAgentCommand,
    ListAgents,
)
from idp_config_registry.application.use_cases.assets import (
    CreateAsset,
    CreateAssetCommand,
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


async def _create_tenant_and_asset(
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


async def test_create_agent_persists_entity_under_existing_asset() -> None:
    unit_of_work_factory = InMemoryUnitOfWorkFactory()
    await _create_tenant_and_asset(unit_of_work_factory)

    agent = await CreateAgent(unit_of_work_factory()).execute(
        CreateAgentCommand(
            tenant_id="tenant-a",
            asset_id="asset-a",
            agent_id="agent-a",
            name="Agent A",
            bootstrap_hint_json={"mqtt_profile": "local"},
        )
    )
    agents = await ListAgents(unit_of_work_factory()).execute(
        "tenant-a",
        "asset-a",
    )

    assert agent.agent_id == "agent-a"
    assert agent.bootstrap_hint_json == {"mqtt_profile": "local"}
    assert agents == [agent]


async def test_create_agent_rejects_missing_asset() -> None:
    unit_of_work_factory = InMemoryUnitOfWorkFactory()

    with pytest.raises(AssetNotFoundError):
        await CreateAgent(unit_of_work_factory()).execute(
            CreateAgentCommand(
                tenant_id="tenant-a",
                asset_id="asset-a",
                agent_id="agent-a",
            )
        )


async def test_create_agent_rejects_duplicate_agent_id_in_asset() -> None:
    unit_of_work_factory = InMemoryUnitOfWorkFactory()
    await _create_tenant_and_asset(unit_of_work_factory)
    command = CreateAgentCommand(
        tenant_id="tenant-a",
        asset_id="asset-a",
        agent_id="agent-a",
    )

    await CreateAgent(unit_of_work_factory()).execute(command)
    with pytest.raises(DuplicateAgentError):
        await CreateAgent(unit_of_work_factory()).execute(command)


async def test_create_agent_rejects_invalid_agent_id() -> None:
    unit_of_work_factory = InMemoryUnitOfWorkFactory()
    await _create_tenant_and_asset(unit_of_work_factory)

    with pytest.raises(DomainValidationError):
        await CreateAgent(unit_of_work_factory()).execute(
            CreateAgentCommand(
                tenant_id="tenant-a",
                asset_id="asset-a",
                agent_id="Agent A",
            )
        )


async def test_list_agents_rejects_missing_asset() -> None:
    unit_of_work_factory = InMemoryUnitOfWorkFactory()

    with pytest.raises(AssetNotFoundError):
        await ListAgents(unit_of_work_factory()).execute("tenant-a", "asset-a")
