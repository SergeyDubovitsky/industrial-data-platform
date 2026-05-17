from __future__ import annotations

from dataclasses import dataclass, replace

from idp_config_registry.application.errors import (
    AssetHasAgentsError,
    AssetNotFoundError,
    DuplicateAssetError,
    TenantNotFoundError,
)
from idp_config_registry.application.ports.unit_of_work import UnitOfWork
from idp_config_registry.domain.entities import Asset, utc_now
from idp_config_registry.domain.value_objects import AssetStatus


@dataclass(frozen=True)
class CreateAssetCommand:
    tenant_code: str
    asset_code: str
    name: str
    description: str | None = None


@dataclass(frozen=True)
class UpdateAssetCommand:
    tenant_code: str
    asset_code: str
    name: str
    description: str | None
    status: AssetStatus


@dataclass(frozen=True)
class DeleteAssetCommand:
    tenant_code: str
    asset_code: str


class CreateAsset:
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        self._unit_of_work = unit_of_work

    async def execute(self, command: CreateAssetCommand) -> Asset:
        asset = Asset(
            tenant_code=command.tenant_code,
            asset_code=command.asset_code,
            name=command.name,
            description=command.description,
        )

        async with self._unit_of_work as unit_of_work:
            if await unit_of_work.tenants.get(asset.tenant_code) is None:
                raise TenantNotFoundError(asset.tenant_code)
            if await unit_of_work.assets.get(asset.tenant_code, asset.asset_code) is not None:
                raise DuplicateAssetError(asset.tenant_code, asset.asset_code)
            await unit_of_work.assets.add(asset)
            await unit_of_work.commit()

        return asset


class UpdateAsset:
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        self._unit_of_work = unit_of_work

    async def execute(self, command: UpdateAssetCommand) -> Asset:
        async with self._unit_of_work as unit_of_work:
            existing = await unit_of_work.assets.get(
                command.tenant_code,
                command.asset_code,
            )
            if existing is None:
                raise AssetNotFoundError(command.tenant_code, command.asset_code)
            asset = replace(
                existing,
                name=command.name,
                description=command.description,
                status=command.status,
                updated_at=utc_now(),
            )
            await unit_of_work.assets.update(asset)
            await unit_of_work.commit()
        return asset


class DeleteAsset:
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        self._unit_of_work = unit_of_work

    async def execute(self, command: DeleteAssetCommand) -> None:
        async with self._unit_of_work as unit_of_work:
            existing = await unit_of_work.assets.get(
                command.tenant_code,
                command.asset_code,
            )
            if existing is None:
                raise AssetNotFoundError(command.tenant_code, command.asset_code)
            if await unit_of_work.agents.list_for_asset(
                command.tenant_code,
                command.asset_code,
            ):
                raise AssetHasAgentsError(command.tenant_code, command.asset_code)
            await unit_of_work.assets.delete(command.tenant_code, command.asset_code)
            await unit_of_work.commit()


class ListAssets:
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        self._unit_of_work = unit_of_work

    async def execute(self, tenant_code: str) -> list[Asset]:
        async with self._unit_of_work as unit_of_work:
            if await unit_of_work.tenants.get(tenant_code) is None:
                raise TenantNotFoundError(tenant_code)
            return await unit_of_work.assets.list_for_tenant(tenant_code)
