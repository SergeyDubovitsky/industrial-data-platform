from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from idp_config_registry.application.errors import (
    AgentNotFoundError,
    DuplicateSourceError,
    SourceHasChildrenError,
    SourceNotFoundError,
)
from idp_config_registry.application.ports.unit_of_work import UnitOfWork
from idp_config_registry.domain.entities import Source, utc_now


@dataclass(frozen=True)
class CreateSourceCommand:
    tenant_id: str
    asset_id: str
    agent_id: str
    source_id: str
    source_type: str
    enabled: bool = True
    name: str | None = None
    description: str | None = None
    connection_json: dict[str, Any] = field(default_factory=dict)
    acquisition_defaults_json: dict[str, Any] = field(default_factory=dict)
    publish_defaults_json: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class UpdateSourceCommand:
    tenant_id: str
    asset_id: str
    agent_id: str
    source_id: str
    source_type: str
    enabled: bool
    name: str | None = None
    description: str | None = None
    connection_json: dict[str, Any] = field(default_factory=dict)
    acquisition_defaults_json: dict[str, Any] = field(default_factory=dict)
    publish_defaults_json: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DeleteSourceCommand:
    tenant_id: str
    asset_id: str
    agent_id: str
    source_id: str


class CreateSource:
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        self._unit_of_work = unit_of_work

    async def execute(self, command: CreateSourceCommand) -> Source:
        source = Source(
            tenant_id=command.tenant_id,
            asset_id=command.asset_id,
            agent_id=command.agent_id,
            source_id=command.source_id,
            source_type=command.source_type,
            enabled=command.enabled,
            name=command.name,
            description=command.description,
            connection_json=dict(command.connection_json),
            acquisition_defaults_json=dict(command.acquisition_defaults_json),
            publish_defaults_json=dict(command.publish_defaults_json),
        )

        async with self._unit_of_work as unit_of_work:
            if (
                await unit_of_work.agents.get(
                    source.tenant_id,
                    source.asset_id,
                    source.agent_id,
                )
                is None
            ):
                raise AgentNotFoundError(
                    source.tenant_id,
                    source.asset_id,
                    source.agent_id,
                )
            if (
                await unit_of_work.sources.get(
                    source.tenant_id,
                    source.asset_id,
                    source.agent_id,
                    source.source_id,
                )
                is not None
            ):
                raise DuplicateSourceError(
                    source.tenant_id,
                    source.asset_id,
                    source.agent_id,
                    source.source_id,
                )
            await unit_of_work.sources.add(source)
            await unit_of_work.commit()

        return source


class UpdateSource:
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        self._unit_of_work = unit_of_work

    async def execute(self, command: UpdateSourceCommand) -> Source:
        async with self._unit_of_work as unit_of_work:
            existing = await unit_of_work.sources.get(
                command.tenant_id,
                command.asset_id,
                command.agent_id,
                command.source_id,
            )
            if existing is None:
                raise SourceNotFoundError(
                    command.tenant_id,
                    command.asset_id,
                    command.agent_id,
                    command.source_id,
                )
            source = replace(
                existing,
                source_type=command.source_type,
                enabled=command.enabled,
                name=command.name,
                description=command.description,
                connection_json=dict(command.connection_json),
                acquisition_defaults_json=dict(command.acquisition_defaults_json),
                publish_defaults_json=dict(command.publish_defaults_json),
                updated_at=utc_now(),
            )
            await unit_of_work.sources.update(source)
            await unit_of_work.commit()
        return source


class DeleteSource:
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        self._unit_of_work = unit_of_work

    async def execute(self, command: DeleteSourceCommand) -> None:
        async with self._unit_of_work as unit_of_work:
            existing = await unit_of_work.sources.get(
                command.tenant_id,
                command.asset_id,
                command.agent_id,
                command.source_id,
            )
            if existing is None:
                raise SourceNotFoundError(
                    command.tenant_id,
                    command.asset_id,
                    command.agent_id,
                    command.source_id,
                )
            if await unit_of_work.points.list_for_source(
                command.tenant_id,
                command.asset_id,
                command.agent_id,
                command.source_id,
            ):
                raise SourceHasChildrenError(
                    command.tenant_id,
                    command.asset_id,
                    command.agent_id,
                    command.source_id,
                    reason="linked points still exist",
                )
            if await unit_of_work.source_config_revisions.has_any_for_source(
                command.tenant_id,
                command.asset_id,
                command.agent_id,
                command.source_id,
            ):
                raise SourceHasChildrenError(
                    command.tenant_id,
                    command.asset_id,
                    command.agent_id,
                    command.source_id,
                    reason="source config revisions still exist",
                )
            if await unit_of_work.config_outbox.has_any_for_source(
                command.tenant_id,
                command.asset_id,
                command.agent_id,
                command.source_id,
            ):
                raise SourceHasChildrenError(
                    command.tenant_id,
                    command.asset_id,
                    command.agent_id,
                    command.source_id,
                    reason="config outbox records still exist",
                )
            await unit_of_work.sources.delete(
                command.tenant_id,
                command.asset_id,
                command.agent_id,
                command.source_id,
            )
            await unit_of_work.commit()


class ListSources:
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        self._unit_of_work = unit_of_work

    async def execute(
        self,
        tenant_id: str,
        asset_id: str,
        agent_id: str,
    ) -> list[Source]:
        async with self._unit_of_work as unit_of_work:
            if await unit_of_work.agents.get(tenant_id, asset_id, agent_id) is None:
                raise AgentNotFoundError(tenant_id, asset_id, agent_id)
            return await unit_of_work.sources.list_for_agent(
                tenant_id,
                asset_id,
                agent_id,
            )
