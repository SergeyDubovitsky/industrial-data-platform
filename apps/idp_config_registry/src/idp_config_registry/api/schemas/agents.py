from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from idp_config_registry.application.use_cases.registry_graph import (
    DeleteAgentRegistryGraphResult,
)
from idp_config_registry.domain.entities import Agent
from idp_config_registry.domain.value_objects import AgentStatus


class AgentCreateRequest(BaseModel):
    agent_id: str = Field(min_length=1)
    name: str | None = None
    bootstrap_hint_json: dict[str, Any] = Field(default_factory=dict)

    @property
    def agent_code(self) -> str:
        return self.agent_id


class AgentResponse(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    tenant_id: str
    asset_id: str
    agent_id: str
    name: str | None
    status: AgentStatus
    bootstrap_hint_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, agent: Agent) -> AgentResponse:
        return cls(
            tenant_id=agent.tenant_code,
            asset_id=agent.asset_code,
            agent_id=agent.agent_code,
            name=agent.name,
            status=agent.status,
            bootstrap_hint_json=dict(agent.bootstrap_hint_json),
            created_at=agent.created_at,
            updated_at=agent.updated_at,
        )


class AgentRegistryGraphDeleteResponse(BaseModel):
    tenant_id: str
    asset_id: str
    agent_id: str
    config_outbox_records_deleted: int
    source_config_revisions_deleted: int
    agent_runtime_config_revisions_deleted: int
    points_deleted: int
    sources_deleted: int
    agents_deleted: int
    assets_deleted: int
    tenants_deleted: int

    @classmethod
    def from_result(
        cls,
        result: DeleteAgentRegistryGraphResult,
    ) -> AgentRegistryGraphDeleteResponse:
        return cls(
            tenant_id=result.tenant_code,
            asset_id=result.asset_code,
            agent_id=result.agent_code,
            config_outbox_records_deleted=result.config_outbox_records_deleted,
            source_config_revisions_deleted=result.source_config_revisions_deleted,
            agent_runtime_config_revisions_deleted=(
                result.agent_runtime_config_revisions_deleted
            ),
            points_deleted=result.points_deleted,
            sources_deleted=result.sources_deleted,
            agents_deleted=result.agents_deleted,
            assets_deleted=result.assets_deleted,
            tenants_deleted=result.tenants_deleted,
        )
