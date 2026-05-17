from __future__ import annotations

import pytest

from idp_config_registry.application.errors import DuplicateTenantError
from idp_config_registry.application.use_cases.tenants import (
    CreateTenant,
    CreateTenantCommand,
    ListTenants,
)
from idp_config_registry.domain.value_objects import DomainValidationError
from idp_config_registry.infrastructure.memory.unit_of_work import (
    InMemoryUnitOfWorkFactory,
)

pytestmark = pytest.mark.asyncio


async def test_create_tenant_persists_entity_and_commits_unit_of_work() -> None:
    unit_of_work_factory = InMemoryUnitOfWorkFactory()

    tenant = await CreateTenant(unit_of_work_factory()).execute(
        CreateTenantCommand(tenant_code="tenant-a", name="Tenant A")
    )
    tenants = await ListTenants(unit_of_work_factory()).execute()

    assert tenant.tenant_code == "tenant-a"
    assert tenants == [tenant]


async def test_create_tenant_rejects_duplicate_id() -> None:
    unit_of_work_factory = InMemoryUnitOfWorkFactory()
    command = CreateTenantCommand(tenant_code="tenant-a", name="Tenant A")

    await CreateTenant(unit_of_work_factory()).execute(command)
    with pytest.raises(DuplicateTenantError):
        await CreateTenant(unit_of_work_factory()).execute(command)


async def test_create_tenant_rejects_blank_name() -> None:
    unit_of_work_factory = InMemoryUnitOfWorkFactory()

    with pytest.raises(DomainValidationError):
        await CreateTenant(unit_of_work_factory()).execute(
            CreateTenantCommand(tenant_code="tenant-a", name=" ")
        )
