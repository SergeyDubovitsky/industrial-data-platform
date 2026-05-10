from __future__ import annotations

import pytest

from idp_config_registry.application.errors import (
    DuplicateAssetError,
    TenantNotFoundError,
)
from idp_config_registry.application.use_cases.assets import (
    CreateAsset,
    CreateAssetCommand,
    ListAssets,
)
from idp_config_registry.application.use_cases.tenants import (
    CreateTenant,
    CreateTenantCommand,
)
from idp_config_registry.domain.value_objects import DomainValidationError
from idp_config_registry.infrastructure.memory.unit_of_work import (
    InMemoryUnitOfWorkFactory,
)

pytestmark = pytest.mark.asyncio


async def test_create_asset_persists_entity_under_existing_tenant() -> None:
    unit_of_work_factory = InMemoryUnitOfWorkFactory()
    await CreateTenant(unit_of_work_factory()).execute(
        CreateTenantCommand(tenant_id="tenant-a", name="Tenant A")
    )

    asset = await CreateAsset(unit_of_work_factory()).execute(
        CreateAssetCommand(
            tenant_id="tenant-a",
            asset_id="asset-a",
            name="Asset A",
            description="Primary monitored asset",
        )
    )
    assets = await ListAssets(unit_of_work_factory()).execute("tenant-a")

    assert asset.asset_id == "asset-a"
    assert asset.description == "Primary monitored asset"
    assert assets == [asset]


async def test_create_asset_rejects_missing_tenant() -> None:
    unit_of_work_factory = InMemoryUnitOfWorkFactory()

    with pytest.raises(TenantNotFoundError):
        await CreateAsset(unit_of_work_factory()).execute(
            CreateAssetCommand(
                tenant_id="tenant-a",
                asset_id="asset-a",
                name="Asset A",
            )
        )


async def test_create_asset_rejects_duplicate_asset_id_in_tenant() -> None:
    unit_of_work_factory = InMemoryUnitOfWorkFactory()
    await CreateTenant(unit_of_work_factory()).execute(
        CreateTenantCommand(tenant_id="tenant-a", name="Tenant A")
    )
    command = CreateAssetCommand(
        tenant_id="tenant-a",
        asset_id="asset-a",
        name="Asset A",
    )

    await CreateAsset(unit_of_work_factory()).execute(command)
    with pytest.raises(DuplicateAssetError):
        await CreateAsset(unit_of_work_factory()).execute(command)


async def test_create_asset_rejects_invalid_asset_id() -> None:
    unit_of_work_factory = InMemoryUnitOfWorkFactory()
    await CreateTenant(unit_of_work_factory()).execute(
        CreateTenantCommand(tenant_id="tenant-a", name="Tenant A")
    )

    with pytest.raises(DomainValidationError):
        await CreateAsset(unit_of_work_factory()).execute(
            CreateAssetCommand(
                tenant_id="tenant-a",
                asset_id="Asset A",
                name="Asset A",
            )
        )


async def test_list_assets_rejects_missing_tenant() -> None:
    unit_of_work_factory = InMemoryUnitOfWorkFactory()

    with pytest.raises(TenantNotFoundError):
        await ListAssets(unit_of_work_factory()).execute("tenant-a")
