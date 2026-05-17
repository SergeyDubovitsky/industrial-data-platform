from __future__ import annotations

from dataclasses import dataclass, replace

from idp_config_registry.application.errors import (
    DuplicateTenantError,
    TenantHasAssetsError,
    TenantNotFoundError,
)
from idp_config_registry.application.ports.unit_of_work import UnitOfWork
from idp_config_registry.domain.entities import Tenant, utc_now
from idp_config_registry.domain.value_objects import TenantStatus


@dataclass(frozen=True)
class CreateTenantCommand:
    tenant_code: str
    name: str


@dataclass(frozen=True)
class UpdateTenantCommand:
    tenant_code: str
    name: str
    status: TenantStatus


@dataclass(frozen=True)
class DeleteTenantCommand:
    tenant_code: str


class CreateTenant:
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        self._unit_of_work = unit_of_work

    async def execute(self, command: CreateTenantCommand) -> Tenant:
        tenant = Tenant(tenant_code=command.tenant_code, name=command.name)

        async with self._unit_of_work as unit_of_work:
            if await unit_of_work.tenants.get(tenant.tenant_code) is not None:
                raise DuplicateTenantError(tenant.tenant_code)
            await unit_of_work.tenants.add(tenant)
            await unit_of_work.commit()

        return tenant


class UpdateTenant:
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        self._unit_of_work = unit_of_work

    async def execute(self, command: UpdateTenantCommand) -> Tenant:
        async with self._unit_of_work as unit_of_work:
            existing = await unit_of_work.tenants.get(command.tenant_code)
            if existing is None:
                raise TenantNotFoundError(command.tenant_code)
            tenant = replace(
                existing,
                name=command.name,
                status=command.status,
                updated_at=utc_now(),
            )
            await unit_of_work.tenants.update(tenant)
            await unit_of_work.commit()
        return tenant


class DeleteTenant:
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        self._unit_of_work = unit_of_work

    async def execute(self, command: DeleteTenantCommand) -> None:
        async with self._unit_of_work as unit_of_work:
            existing = await unit_of_work.tenants.get(command.tenant_code)
            if existing is None:
                raise TenantNotFoundError(command.tenant_code)
            if await unit_of_work.assets.list_for_tenant(command.tenant_code):
                raise TenantHasAssetsError(command.tenant_code)
            await unit_of_work.tenants.delete(command.tenant_code)
            await unit_of_work.commit()


class ListTenants:
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        self._unit_of_work = unit_of_work

    async def execute(self) -> list[Tenant]:
        async with self._unit_of_work as unit_of_work:
            return await unit_of_work.tenants.list()
