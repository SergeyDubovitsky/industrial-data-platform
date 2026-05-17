from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from idp_config_registry.domain.entities import Source


class SourceCreateRequest(BaseModel):
    source_id: str = Field(min_length=1)
    source_type: str = Field(min_length=1)
    enabled: bool = True
    name: str | None = None
    description: str | None = None
    connection_json: dict[str, Any] = Field(default_factory=dict)
    acquisition_defaults_json: dict[str, Any] = Field(default_factory=dict)
    publish_defaults_json: dict[str, Any] = Field(default_factory=dict)


class SourceResponse(BaseModel):
    tenant_id: str
    asset_id: str
    agent_id: str
    source_id: str
    source_type: str
    enabled: bool
    name: str | None
    description: str | None
    connection_json: dict[str, Any]
    acquisition_defaults_json: dict[str, Any]
    publish_defaults_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, source: Source) -> SourceResponse:
        return cls(
            tenant_id=source.tenant_code,
            asset_id=source.asset_code,
            agent_id=source.agent_code,
            source_id=source.source_code,
            source_type=source.source_type,
            enabled=source.enabled,
            name=source.name,
            description=source.description,
            connection_json=dict(source.connection_json),
            acquisition_defaults_json=dict(source.acquisition_defaults_json),
            publish_defaults_json=dict(source.publish_defaults_json),
            created_at=source.created_at,
            updated_at=source.updated_at,
        )
