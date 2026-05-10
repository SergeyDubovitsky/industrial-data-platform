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
    tenant_id: str
    asset_id: str
    name: str
    description: str | None = None


@dataclass(frozen=True)
class UpdateAssetCommand:
    tenant_id: str
    asset_id: str
    name: str
    description: str | None
    status: AssetStatus


@dataclass(frozen=True)
class DeleteAssetCommand:
    tenant_id: str
    asset_id: str


class CreateAsset:
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        self._unit_of_work = unit_of_work

    async def execute(self, command: CreateAssetCommand) -> Asset:
        asset = Asset(
            tenant_id=command.tenant_id,
            asset_id=command.asset_id,
            name=command.name,
            description=command.description,
        )

        async with self._unit_of_work as unit_of_work:
            if await unit_of_work.tenants.get(asset.tenant_id) is None:
                raise TenantNotFoundError(asset.tenant_id)
            if await unit_of_work.assets.get(asset.tenant_id, asset.asset_id) is not None:
                raise DuplicateAssetError(asset.tenant_id, asset.asset_id)
            await unit_of_work.assets.add(asset)
            await unit_of_work.commit()

        return asset


class UpdateAsset:
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        self._unit_of_work = unit_of_work

    async def execute(self, command: UpdateAssetCommand) -> Asset:
        async with self._unit_of_work as unit_of_work:
            existing = await unit_of_work.assets.get(
                command.tenant_id,
                command.asset_id,
            )
            if existing is None:
                raise AssetNotFoundError(command.tenant_id, command.asset_id)
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
                command.tenant_id,
                command.asset_id,
            )
            if existing is None:
                raise AssetNotFoundError(command.tenant_id, command.asset_id)
            if await unit_of_work.agents.list_for_asset(
                command.tenant_id,
                command.asset_id,
            ):
                raise AssetHasAgentsError(command.tenant_id, command.asset_id)
            await unit_of_work.assets.delete(command.tenant_id, command.asset_id)
            await unit_of_work.commit()


class ListAssets:
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        self._unit_of_work = unit_of_work

    async def execute(self, tenant_id: str) -> list[Asset]:
        async with self._unit_of_work as unit_of_work:
            if await unit_of_work.tenants.get(tenant_id) is None:
                raise TenantNotFoundError(tenant_id)
            return await unit_of_work.assets.list_for_tenant(tenant_id)
