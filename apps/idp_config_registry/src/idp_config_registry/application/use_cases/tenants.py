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
    tenant_id: str
    name: str


@dataclass(frozen=True)
class UpdateTenantCommand:
    tenant_id: str
    name: str
    status: TenantStatus


@dataclass(frozen=True)
class DeleteTenantCommand:
    tenant_id: str


class CreateTenant:
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        self._unit_of_work = unit_of_work

    async def execute(self, command: CreateTenantCommand) -> Tenant:
        tenant = Tenant(tenant_id=command.tenant_id, name=command.name)

        async with self._unit_of_work as unit_of_work:
            if await unit_of_work.tenants.get(tenant.tenant_id) is not None:
                raise DuplicateTenantError(tenant.tenant_id)
            await unit_of_work.tenants.add(tenant)
            await unit_of_work.commit()

        return tenant


class UpdateTenant:
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        self._unit_of_work = unit_of_work

    async def execute(self, command: UpdateTenantCommand) -> Tenant:
        async with self._unit_of_work as unit_of_work:
            existing = await unit_of_work.tenants.get(command.tenant_id)
            if existing is None:
                raise TenantNotFoundError(command.tenant_id)
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
            existing = await unit_of_work.tenants.get(command.tenant_id)
            if existing is None:
                raise TenantNotFoundError(command.tenant_id)
            if await unit_of_work.assets.list_for_tenant(command.tenant_id):
                raise TenantHasAssetsError(command.tenant_id)
            await unit_of_work.tenants.delete(command.tenant_id)
            await unit_of_work.commit()


class ListTenants:
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        self._unit_of_work = unit_of_work

    async def execute(self) -> list[Tenant]:
        async with self._unit_of_work as unit_of_work:
            return await unit_of_work.tenants.list()
