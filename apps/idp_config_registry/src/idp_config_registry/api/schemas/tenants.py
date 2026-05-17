from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from idp_config_registry.domain.entities import Tenant
from idp_config_registry.domain.value_objects import TenantStatus


class TenantCreateRequest(BaseModel):
    tenant_id: str = Field(min_length=1)
    name: str = Field(min_length=1)


class TenantResponse(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    tenant_id: str
    name: str
    status: TenantStatus
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, tenant: Tenant) -> TenantResponse:
        return cls(
            tenant_id=tenant.tenant_code,
            name=tenant.name,
            status=tenant.status,
            created_at=tenant.created_at,
            updated_at=tenant.updated_at,
        )
