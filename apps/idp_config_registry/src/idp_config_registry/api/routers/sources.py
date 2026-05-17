from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from idp_config_registry.api.dependencies import (
    UnitOfWorkFactory,
    get_unit_of_work_factory,
)
from idp_config_registry.api.schemas.sources import SourceCreateRequest, SourceResponse
from idp_config_registry.application.errors import (
    AgentNotFoundError,
    DuplicateSourceError,
)
from idp_config_registry.application.use_cases.sources import (
    CreateSource,
    CreateSourceCommand,
    ListSources,
)
from idp_config_registry.domain.value_objects import DomainValidationError

router = APIRouter(
    prefix="/tenants/{tenant_id}/assets/{asset_id}/agents/{agent_id}/sources",
    tags=["sources"],
)


@router.post(
    "",
    response_model=SourceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_source(
    tenant_id: str,
    asset_id: str,
    agent_id: str,
    request: SourceCreateRequest,
    unit_of_work_factory: UnitOfWorkFactory = Depends(get_unit_of_work_factory),
) -> SourceResponse:
    tenant_code = tenant_id
    asset_code = asset_id
    agent_code = agent_id
    source_code = request.source_id
    try:
        source = await CreateSource(unit_of_work_factory()).execute(
            CreateSourceCommand(
                tenant_code=tenant_code,
                asset_code=asset_code,
                agent_code=agent_code,
                source_code=source_code,
                source_type=request.source_type,
                enabled=request.enabled,
                name=request.name,
                description=request.description,
                connection_json=request.connection_json,
                acquisition_defaults_json=request.acquisition_defaults_json,
                publish_defaults_json=request.publish_defaults_json,
            )
        )
    except AgentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except DuplicateSourceError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except DomainValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    return SourceResponse.from_domain(source)


@router.get("", response_model=list[SourceResponse])
async def list_sources(
    tenant_id: str,
    asset_id: str,
    agent_id: str,
    unit_of_work_factory: UnitOfWorkFactory = Depends(get_unit_of_work_factory),
) -> list[SourceResponse]:
    tenant_code = tenant_id
    asset_code = asset_id
    agent_code = agent_id
    try:
        sources = await ListSources(unit_of_work_factory()).execute(
            tenant_code,
            asset_code,
            agent_code,
        )
    except AgentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return [SourceResponse.from_domain(source) for source in sources]
