from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from idp_config_registry.api.dependencies import (
    UnitOfWorkFactory,
    get_unit_of_work_factory,
)
from idp_config_registry.api.schemas.points import PointCreateRequest, PointResponse
from idp_config_registry.application.errors import (
    DuplicatePointError,
    PointNotFoundError,
    SourceNotFoundError,
)
from idp_config_registry.application.use_cases.points import (
    CreatePoint,
    CreatePointCommand,
    DeletePoint,
    DeletePointCommand,
    ListPoints,
)
from idp_config_registry.domain.value_objects import DomainValidationError

router = APIRouter(
    prefix=(
        "/tenants/{tenant_id}/assets/{asset_id}/agents/{agent_id}"
        "/sources/{source_id}/points"
    ),
    tags=["points"],
)


@router.post(
    "",
    response_model=PointResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_point(
    tenant_id: str,
    asset_id: str,
    agent_id: str,
    source_id: str,
    request: PointCreateRequest,
    unit_of_work_factory: UnitOfWorkFactory = Depends(get_unit_of_work_factory),
) -> PointResponse:
    try:
        point = await CreatePoint(unit_of_work_factory()).execute(
            CreatePointCommand(
                tenant_id=tenant_id,
                asset_id=asset_id,
                agent_id=agent_id,
                source_id=source_id,
                point_id=request.point_id,
                point_key=request.point_key,
                point_ref=request.point_ref,
                name=request.name,
                value_type=request.value_type,
                value_model=request.value_model,
                signal_type=request.signal_type,
                description=request.description,
                unit=request.unit,
                enabled=request.enabled,
                acquisition_json=request.acquisition_json,
                publish_json=request.publish_json,
                tags_json=request.tags_json,
            )
        )
    except SourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except DuplicatePointError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except DomainValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    return PointResponse.from_domain(point)


@router.get("", response_model=list[PointResponse])
async def list_points(
    tenant_id: str,
    asset_id: str,
    agent_id: str,
    source_id: str,
    unit_of_work_factory: UnitOfWorkFactory = Depends(get_unit_of_work_factory),
) -> list[PointResponse]:
    try:
        points = await ListPoints(unit_of_work_factory()).execute(
            tenant_id,
            asset_id,
            agent_id,
            source_id,
        )
    except SourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return [PointResponse.from_domain(point) for point in points]


@router.delete(
    "/{point_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_point(
    tenant_id: str,
    asset_id: str,
    agent_id: str,
    source_id: str,
    point_id: str,
    unit_of_work_factory: UnitOfWorkFactory = Depends(get_unit_of_work_factory),
) -> None:
    try:
        await DeletePoint(unit_of_work_factory()).execute(
            DeletePointCommand(
                tenant_id=tenant_id,
                asset_id=asset_id,
                agent_id=agent_id,
                source_id=source_id,
                point_id=point_id,
            )
        )
    except PointNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
