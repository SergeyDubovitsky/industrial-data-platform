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
    tenant_code: str
    asset_code: str
    agent_code: str
    source_code: str
    source_type: str
    enabled: bool = True
    name: str | None = None
    description: str | None = None
    connection_json: dict[str, Any] = field(default_factory=dict)
    acquisition_defaults_json: dict[str, Any] = field(default_factory=dict)
    publish_defaults_json: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class UpdateSourceCommand:
    tenant_code: str
    asset_code: str
    agent_code: str
    source_code: str
    source_type: str
    enabled: bool
    name: str | None = None
    description: str | None = None
    connection_json: dict[str, Any] = field(default_factory=dict)
    acquisition_defaults_json: dict[str, Any] = field(default_factory=dict)
    publish_defaults_json: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DeleteSourceCommand:
    tenant_code: str
    asset_code: str
    agent_code: str
    source_code: str


class CreateSource:
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        self._unit_of_work = unit_of_work

    async def execute(self, command: CreateSourceCommand) -> Source:
        source = Source(
            tenant_code=command.tenant_code,
            asset_code=command.asset_code,
            agent_code=command.agent_code,
            source_code=command.source_code,
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
                    source.tenant_code,
                    source.asset_code,
                    source.agent_code,
                )
                is None
            ):
                raise AgentNotFoundError(
                    source.tenant_code,
                    source.asset_code,
                    source.agent_code,
                )
            if (
                await unit_of_work.sources.get(
                    source.tenant_code,
                    source.asset_code,
                    source.agent_code,
                    source.source_code,
                )
                is not None
            ):
                raise DuplicateSourceError(
                    source.tenant_code,
                    source.asset_code,
                    source.agent_code,
                    source.source_code,
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
                command.tenant_code,
                command.asset_code,
                command.agent_code,
                command.source_code,
            )
            if existing is None:
                raise SourceNotFoundError(
                    command.tenant_code,
                    command.asset_code,
                    command.agent_code,
                    command.source_code,
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
                command.tenant_code,
                command.asset_code,
                command.agent_code,
                command.source_code,
            )
            if existing is None:
                raise SourceNotFoundError(
                    command.tenant_code,
                    command.asset_code,
                    command.agent_code,
                    command.source_code,
                )
            if await unit_of_work.points.list_for_source(
                command.tenant_code,
                command.asset_code,
                command.agent_code,
                command.source_code,
            ):
                raise SourceHasChildrenError(
                    command.tenant_code,
                    command.asset_code,
                    command.agent_code,
                    command.source_code,
                    reason="linked points still exist",
                )
            if await unit_of_work.source_config_revisions.has_any_for_source(
                command.tenant_code,
                command.asset_code,
                command.agent_code,
                command.source_code,
            ):
                raise SourceHasChildrenError(
                    command.tenant_code,
                    command.asset_code,
                    command.agent_code,
                    command.source_code,
                    reason="source config revisions still exist",
                )
            if await unit_of_work.config_outbox.has_any_for_source(
                command.tenant_code,
                command.asset_code,
                command.agent_code,
                command.source_code,
            ):
                raise SourceHasChildrenError(
                    command.tenant_code,
                    command.asset_code,
                    command.agent_code,
                    command.source_code,
                    reason="config outbox records still exist",
                )
            await unit_of_work.sources.delete(
                command.tenant_code,
                command.asset_code,
                command.agent_code,
                command.source_code,
            )
            await unit_of_work.commit()


class ListSources:
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        self._unit_of_work = unit_of_work

    async def execute(
        self,
        tenant_code: str,
        asset_code: str,
        agent_code: str,
    ) -> list[Source]:
        async with self._unit_of_work as unit_of_work:
            if await unit_of_work.agents.get(tenant_code, asset_code, agent_code) is None:
                raise AgentNotFoundError(tenant_code, asset_code, agent_code)
            return await unit_of_work.sources.list_for_agent(
                tenant_code,
                asset_code,
                agent_code,
            )
