from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from idp_config_registry.application.errors import (
    AgentNotFoundError,
    DuplicateConfigRevisionError,
    DuplicateSourceConfigRevisionError,
    SourceNotFoundError,
)
from idp_config_registry.application.ports.unit_of_work import UnitOfWork
from idp_config_registry.domain.entities import (
    AgentRuntimeConfigRevision,
    SourceConfigRevision,
)
from idp_config_registry.domain.value_objects import ConfigRevisionStatus


@dataclass(frozen=True)
class CreateAgentRuntimeConfigRevisionCommand:
    tenant_code: str
    asset_code: str
    agent_code: str
    config_revision: str
    issued_at: datetime
    agent_runtime_payload_json: dict[str, Any] = field(default_factory=dict)
    status: ConfigRevisionStatus = ConfigRevisionStatus.DRAFT


class CreateAgentRuntimeConfigRevision:
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        self._unit_of_work = unit_of_work

    async def execute(
        self,
        command: CreateAgentRuntimeConfigRevisionCommand,
    ) -> AgentRuntimeConfigRevision:
        revision = AgentRuntimeConfigRevision(
            tenant_code=command.tenant_code,
            asset_code=command.asset_code,
            agent_code=command.agent_code,
            config_revision=command.config_revision,
            issued_at=command.issued_at,
            agent_runtime_payload_json=dict(command.agent_runtime_payload_json),
            status=command.status,
        )

        async with self._unit_of_work as unit_of_work:
            if (
                await unit_of_work.agents.get(
                    revision.tenant_code,
                    revision.asset_code,
                    revision.agent_code,
                )
                is None
            ):
                raise AgentNotFoundError(
                    revision.tenant_code,
                    revision.asset_code,
                    revision.agent_code,
                )
            if (
                await unit_of_work.agent_runtime_config_revisions.get(
                    revision.tenant_code,
                    revision.asset_code,
                    revision.agent_code,
                    revision.config_revision,
                )
                is not None
            ):
                raise DuplicateConfigRevisionError(
                    revision.tenant_code,
                    revision.asset_code,
                    revision.agent_code,
                    revision.config_revision,
                )
            await unit_of_work.agent_runtime_config_revisions.add(revision)
            await unit_of_work.commit()

        return revision


@dataclass(frozen=True)
class CreateSourceConfigRevisionCommand:
    tenant_code: str
    asset_code: str
    agent_code: str
    source_code: str
    source_config_revision: str
    config_revision: str
    issued_at: datetime
    source_payload_json: dict[str, Any] = field(default_factory=dict)
    status: ConfigRevisionStatus = ConfigRevisionStatus.DRAFT


class CreateSourceConfigRevision:
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        self._unit_of_work = unit_of_work

    async def execute(
        self,
        command: CreateSourceConfigRevisionCommand,
    ) -> SourceConfigRevision:
        revision = SourceConfigRevision(
            tenant_code=command.tenant_code,
            asset_code=command.asset_code,
            agent_code=command.agent_code,
            source_code=command.source_code,
            source_config_revision=command.source_config_revision,
            config_revision=command.config_revision,
            issued_at=command.issued_at,
            source_payload_json=dict(command.source_payload_json),
            status=command.status,
        )

        async with self._unit_of_work as unit_of_work:
            if (
                await unit_of_work.sources.get(
                    revision.tenant_code,
                    revision.asset_code,
                    revision.agent_code,
                    revision.source_code,
                )
                is None
            ):
                raise SourceNotFoundError(
                    revision.tenant_code,
                    revision.asset_code,
                    revision.agent_code,
                    revision.source_code,
                )
            if (
                await unit_of_work.source_config_revisions.get(
                    revision.tenant_code,
                    revision.asset_code,
                    revision.agent_code,
                    revision.source_code,
                    revision.source_config_revision,
                )
                is not None
            ):
                raise DuplicateSourceConfigRevisionError(
                    revision.tenant_code,
                    revision.asset_code,
                    revision.agent_code,
                    revision.source_code,
                    revision.source_config_revision,
                )
            await unit_of_work.source_config_revisions.add(revision)
            await unit_of_work.commit()

        return revision
