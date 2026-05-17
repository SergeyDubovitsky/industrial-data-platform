from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from idp_config_registry.api.dependencies import (
    UnitOfWorkFactory,
    get_unit_of_work_factory,
)
from idp_config_registry.api.path_params import TenantCodePath
from idp_config_registry.api.schemas.assets import AssetCreateRequest, AssetResponse
from idp_config_registry.application.errors import (
    DuplicateAssetError,
    TenantNotFoundError,
)
from idp_config_registry.application.use_cases.assets import (
    CreateAsset,
    CreateAssetCommand,
    ListAssets,
)
from idp_config_registry.domain.value_objects import DomainValidationError

router = APIRouter(prefix="/tenants/{tenant_id}/assets", tags=["assets"])


@router.post(
    "",
    response_model=AssetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_asset(
    tenant_code: TenantCodePath,
    request: AssetCreateRequest,
    unit_of_work_factory: UnitOfWorkFactory = Depends(get_unit_of_work_factory),
) -> AssetResponse:
    try:
        asset = await CreateAsset(unit_of_work_factory()).execute(
            CreateAssetCommand(
                tenant_code=tenant_code,
                asset_code=request.asset_code,
                name=request.name,
                description=request.description,
            )
        )
    except TenantNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except DuplicateAssetError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except DomainValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    return AssetResponse.from_domain(asset)


@router.get("", response_model=list[AssetResponse])
async def list_assets(
    tenant_code: TenantCodePath,
    unit_of_work_factory: UnitOfWorkFactory = Depends(get_unit_of_work_factory),
) -> list[AssetResponse]:
    try:
        assets = await ListAssets(unit_of_work_factory()).execute(tenant_code)
    except TenantNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return [AssetResponse.from_domain(asset) for asset in assets]
