from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from idp_config_registry.application.errors import (
    AgentHasChildrenError,
    AgentNotFoundError,
    AssetNotFoundError,
    DuplicateAgentError,
)
from idp_config_registry.application.ports.unit_of_work import UnitOfWork
from idp_config_registry.domain.entities import Agent, utc_now
from idp_config_registry.domain.value_objects import AgentStatus


@dataclass(frozen=True)
class CreateAgentCommand:
    tenant_id: str
    asset_id: str
    agent_id: str
    name: str | None = None
    bootstrap_hint_json: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class UpdateAgentCommand:
    tenant_id: str
    asset_id: str
    agent_id: str
    name: str | None
    status: AgentStatus
    bootstrap_hint_json: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DeleteAgentCommand:
    tenant_id: str
    asset_id: str
    agent_id: str


class CreateAgent:
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        self._unit_of_work = unit_of_work

    async def execute(self, command: CreateAgentCommand) -> Agent:
        agent = Agent(
            tenant_id=command.tenant_id,
            asset_id=command.asset_id,
            agent_id=command.agent_id,
            name=command.name,
            bootstrap_hint_json=dict(command.bootstrap_hint_json),
        )

        async with self._unit_of_work as unit_of_work:
            if await unit_of_work.assets.get(agent.tenant_id, agent.asset_id) is None:
                raise AssetNotFoundError(agent.tenant_id, agent.asset_id)
            if (
                await unit_of_work.agents.get(
                    agent.tenant_id,
                    agent.asset_id,
                    agent.agent_id,
                )
                is not None
            ):
                raise DuplicateAgentError(
                    agent.tenant_id,
                    agent.asset_id,
                    agent.agent_id,
                )
            await unit_of_work.agents.add(agent)
            await unit_of_work.commit()

        return agent


class UpdateAgent:
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        self._unit_of_work = unit_of_work

    async def execute(self, command: UpdateAgentCommand) -> Agent:
        async with self._unit_of_work as unit_of_work:
            existing = await unit_of_work.agents.get(
                command.tenant_id,
                command.asset_id,
                command.agent_id,
            )
            if existing is None:
                raise AgentNotFoundError(
                    command.tenant_id,
                    command.asset_id,
                    command.agent_id,
                )
            agent = replace(
                existing,
                name=command.name,
                status=command.status,
                bootstrap_hint_json=dict(command.bootstrap_hint_json),
                updated_at=utc_now(),
            )
            await unit_of_work.agents.update(agent)
            await unit_of_work.commit()
        return agent


class DeleteAgent:
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        self._unit_of_work = unit_of_work

    async def execute(self, command: DeleteAgentCommand) -> None:
        async with self._unit_of_work as unit_of_work:
            existing = await unit_of_work.agents.get(
                command.tenant_id,
                command.asset_id,
                command.agent_id,
            )
            if existing is None:
                raise AgentNotFoundError(
                    command.tenant_id,
                    command.asset_id,
                    command.agent_id,
                )
            if await unit_of_work.sources.list_for_agent(
                command.tenant_id,
                command.asset_id,
                command.agent_id,
            ):
                raise AgentHasChildrenError(
                    command.tenant_id,
                    command.asset_id,
                    command.agent_id,
                    reason="linked sources still exist",
                )
            if await unit_of_work.agent_runtime_config_revisions.has_any_for_agent(
                command.tenant_id,
                command.asset_id,
                command.agent_id,
            ):
                raise AgentHasChildrenError(
                    command.tenant_id,
                    command.asset_id,
                    command.agent_id,
                    reason="agent runtime config revisions still exist",
                )
            if await unit_of_work.config_outbox.has_any_for_agent(
                command.tenant_id,
                command.asset_id,
                command.agent_id,
            ):
                raise AgentHasChildrenError(
                    command.tenant_id,
                    command.asset_id,
                    command.agent_id,
                    reason="config outbox records still exist",
                )
            await unit_of_work.agents.delete(
                command.tenant_id,
                command.asset_id,
                command.agent_id,
            )
            await unit_of_work.commit()


class ListAgents:
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        self._unit_of_work = unit_of_work

    async def execute(self, tenant_id: str, asset_id: str) -> list[Agent]:
        async with self._unit_of_work as unit_of_work:
            if await unit_of_work.assets.get(tenant_id, asset_id) is None:
                raise AssetNotFoundError(tenant_id, asset_id)
            return await unit_of_work.agents.list_for_asset(tenant_id, asset_id)
