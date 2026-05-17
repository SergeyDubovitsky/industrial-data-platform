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
    tenant_code: str
    asset_code: str
    agent_code: str
    name: str | None = None
    bootstrap_hint_json: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class UpdateAgentCommand:
    tenant_code: str
    asset_code: str
    agent_code: str
    name: str | None
    status: AgentStatus
    bootstrap_hint_json: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DeleteAgentCommand:
    tenant_code: str
    asset_code: str
    agent_code: str


class CreateAgent:
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        self._unit_of_work = unit_of_work

    async def execute(self, command: CreateAgentCommand) -> Agent:
        agent = Agent(
            tenant_code=command.tenant_code,
            asset_code=command.asset_code,
            agent_code=command.agent_code,
            name=command.name,
            bootstrap_hint_json=dict(command.bootstrap_hint_json),
        )

        async with self._unit_of_work as unit_of_work:
            if await unit_of_work.assets.get(agent.tenant_code, agent.asset_code) is None:
                raise AssetNotFoundError(agent.tenant_code, agent.asset_code)
            if (
                await unit_of_work.agents.get(
                    agent.tenant_code,
                    agent.asset_code,
                    agent.agent_code,
                )
                is not None
            ):
                raise DuplicateAgentError(
                    agent.tenant_code,
                    agent.asset_code,
                    agent.agent_code,
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
                command.tenant_code,
                command.asset_code,
                command.agent_code,
            )
            if existing is None:
                raise AgentNotFoundError(
                    command.tenant_code,
                    command.asset_code,
                    command.agent_code,
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
                command.tenant_code,
                command.asset_code,
                command.agent_code,
            )
            if existing is None:
                raise AgentNotFoundError(
                    command.tenant_code,
                    command.asset_code,
                    command.agent_code,
                )
            if await unit_of_work.sources.list_for_agent(
                command.tenant_code,
                command.asset_code,
                command.agent_code,
            ):
                raise AgentHasChildrenError(
                    command.tenant_code,
                    command.asset_code,
                    command.agent_code,
                    reason="linked sources still exist",
                )
            if await unit_of_work.agent_runtime_config_revisions.has_any_for_agent(
                command.tenant_code,
                command.asset_code,
                command.agent_code,
            ):
                raise AgentHasChildrenError(
                    command.tenant_code,
                    command.asset_code,
                    command.agent_code,
                    reason="agent runtime config revisions still exist",
                )
            if await unit_of_work.config_outbox.has_any_for_agent(
                command.tenant_code,
                command.asset_code,
                command.agent_code,
            ):
                raise AgentHasChildrenError(
                    command.tenant_code,
                    command.asset_code,
                    command.agent_code,
                    reason="config outbox records still exist",
                )
            await unit_of_work.agents.delete(
                command.tenant_code,
                command.asset_code,
                command.agent_code,
            )
            await unit_of_work.commit()


class ListAgents:
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        self._unit_of_work = unit_of_work

    async def execute(self, tenant_code: str, asset_code: str) -> list[Agent]:
        async with self._unit_of_work as unit_of_work:
            if await unit_of_work.assets.get(tenant_code, asset_code) is None:
                raise AssetNotFoundError(tenant_code, asset_code)
            return await unit_of_work.agents.list_for_asset(tenant_code, asset_code)
