from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from idp_config_registry.domain.entities import Asset
from idp_config_registry.domain.value_objects import AssetStatus


class AssetCreateRequest(BaseModel):
    asset_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str | None = None


class AssetResponse(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    tenant_id: str
    asset_id: str
    name: str
    description: str | None
    status: AssetStatus
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, asset: Asset) -> AssetResponse:
        return cls(
            tenant_id=asset.tenant_code,
            asset_id=asset.asset_code,
            name=asset.name,
            description=asset.description,
            status=asset.status,
            created_at=asset.created_at,
            updated_at=asset.updated_at,
        )
