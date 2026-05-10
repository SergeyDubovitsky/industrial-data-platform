from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from idp_config_registry.domain.entities import Agent
from idp_config_registry.domain.value_objects import AgentStatus


class AgentCreateRequest(BaseModel):
    agent_id: str = Field(min_length=1)
    name: str | None = None
    bootstrap_hint_json: dict[str, Any] = Field(default_factory=dict)


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
            tenant_id=agent.tenant_id,
            asset_id=agent.asset_id,
            agent_id=agent.agent_id,
            name=agent.name,
            status=agent.status,
            bootstrap_hint_json=dict(agent.bootstrap_hint_json),
            created_at=agent.created_at,
            updated_at=agent.updated_at,
        )
