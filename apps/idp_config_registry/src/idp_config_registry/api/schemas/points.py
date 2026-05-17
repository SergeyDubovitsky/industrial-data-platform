from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from idp_config_registry.domain.entities import Point
from idp_config_registry.domain.value_objects import SignalType, ValueType


class PointCreateRequest(BaseModel):
    point_id: str = Field(min_length=1)
    point_key: str = Field(min_length=1)
    point_ref: str = Field(min_length=1)
    name: str = Field(min_length=1)
    value_type: ValueType
    value_model: str = Field(min_length=1)
    signal_type: SignalType
    description: str | None = None
    unit: str | None = None
    enabled: bool = True
    acquisition_json: dict[str, Any] = Field(default_factory=dict)
    publish_json: dict[str, Any] = Field(default_factory=dict)
    tags_json: dict[str, Any] = Field(default_factory=dict)


class PointResponse(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    tenant_id: str
    asset_id: str
    agent_id: str
    source_id: str
    point_id: str
    point_key: str
    point_ref: str
    name: str
    description: str | None
    value_type: ValueType
    value_model: str
    signal_type: SignalType
    unit: str | None
    enabled: bool
    acquisition_json: dict[str, Any]
    publish_json: dict[str, Any]
    tags_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, point: Point) -> PointResponse:
        return cls(
            tenant_id=point.tenant_code,
            asset_id=point.asset_code,
            agent_id=point.agent_code,
            source_id=point.source_code,
            point_id=point.point_code,
            point_key=point.point_key,
            point_ref=point.point_ref,
            name=point.name,
            description=point.description,
            value_type=point.value_type,
            value_model=point.value_model,
            signal_type=point.signal_type,
            unit=point.unit,
            enabled=point.enabled,
            acquisition_json=dict(point.acquisition_json),
            publish_json=dict(point.publish_json),
            tags_json=dict(point.tags_json),
            created_at=point.created_at,
            updated_at=point.updated_at,
        )
