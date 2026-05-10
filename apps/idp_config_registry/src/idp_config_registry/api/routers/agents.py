from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from idp_config_registry.api.dependencies import (
    UnitOfWorkFactory,
    get_config_payload_validator,
    get_unit_of_work_factory,
)
from idp_config_registry.api.schemas.agents import AgentCreateRequest, AgentResponse
from idp_config_registry.api.schemas.config_revisions import (
    RenderAgentRuntimeConfigRequest,
    RenderAgentRuntimeConfigResponse,
)
from idp_config_registry.application.errors import (
    AgentNotFoundError,
    AssetNotFoundError,
    ConfigRenderError,
    DuplicateAgentError,
    DuplicateConfigOutboxRecordError,
    DuplicateConfigRevisionError,
)
from idp_config_registry.application.ports.config_validation import (
    ConfigPayloadValidator,
)
from idp_config_registry.application.use_cases.agents import (
    CreateAgent,
    CreateAgentCommand,
    ListAgents,
)
from idp_config_registry.application.use_cases.render_config import (
    RenderAgentRuntimeConfig,
    RenderAgentRuntimeConfigCommand,
    StoreRenderedAgentRuntimeConfig,
)
from idp_config_registry.domain.value_objects import DomainValidationError

router = APIRouter(
    prefix="/tenants/{tenant_id}/assets/{asset_id}/agents",
    tags=["agents"],
)


@router.post(
    "",
    response_model=AgentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_agent(
    tenant_id: str,
    asset_id: str,
    request: AgentCreateRequest,
    unit_of_work_factory: UnitOfWorkFactory = Depends(get_unit_of_work_factory),
) -> AgentResponse:
    try:
        agent = await CreateAgent(unit_of_work_factory()).execute(
            CreateAgentCommand(
                tenant_id=tenant_id,
                asset_id=asset_id,
                agent_id=request.agent_id,
                name=request.name,
                bootstrap_hint_json=request.bootstrap_hint_json,
            )
        )
    except AssetNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except DuplicateAgentError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except DomainValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    return AgentResponse.from_domain(agent)


@router.get("", response_model=list[AgentResponse])
async def list_agents(
    tenant_id: str,
    asset_id: str,
    unit_of_work_factory: UnitOfWorkFactory = Depends(get_unit_of_work_factory),
) -> list[AgentResponse]:
    try:
        agents = await ListAgents(unit_of_work_factory()).execute(tenant_id, asset_id)
    except AssetNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return [AgentResponse.from_domain(agent) for agent in agents]


@router.post(
    "/{agent_id}/render-config",
    response_model=RenderAgentRuntimeConfigResponse,
    status_code=status.HTTP_201_CREATED,
)
async def render_agent_config(
    tenant_id: str,
    asset_id: str,
    agent_id: str,
    request: RenderAgentRuntimeConfigRequest,
    unit_of_work_factory: UnitOfWorkFactory = Depends(get_unit_of_work_factory),
    validator: ConfigPayloadValidator = Depends(get_config_payload_validator),
) -> RenderAgentRuntimeConfigResponse:
    try:
        rendered = await RenderAgentRuntimeConfig(unit_of_work_factory(), validator).execute(
            RenderAgentRuntimeConfigCommand(
                tenant_id=tenant_id,
                asset_id=asset_id,
                agent_id=agent_id,
                config_revision=request.config_revision,
                issued_at=request.issued_at,
                source_config_revisions=request.source_config_revisions,
            )
        )
        await StoreRenderedAgentRuntimeConfig(unit_of_work_factory(), validator).execute(
            rendered
        )
    except AgentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except (DuplicateConfigRevisionError, DuplicateConfigOutboxRecordError) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except ConfigRenderError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    return RenderAgentRuntimeConfigResponse.from_rendered(rendered)
