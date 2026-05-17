from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from idp_config_registry.api.dependencies import (
    UnitOfWorkFactory,
    get_config_payload_validator,
    get_unit_of_work_factory,
)
from idp_config_registry.api.schemas.agents import (
    AgentCreateRequest,
    AgentRegistryGraphDeleteResponse,
    AgentResponse,
)
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
from idp_config_registry.application.use_cases.registry_graph import (
    DeleteAgentRegistryGraph,
    DeleteAgentRegistryGraphCommand,
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
    tenant_code = tenant_id
    asset_code = asset_id
    agent_code = request.agent_id
    try:
        agent = await CreateAgent(unit_of_work_factory()).execute(
            CreateAgentCommand(
                tenant_code=tenant_code,
                asset_code=asset_code,
                agent_code=agent_code,
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
    tenant_code = tenant_id
    asset_code = asset_id
    try:
        agents = await ListAgents(unit_of_work_factory()).execute(
            tenant_code,
            asset_code,
        )
    except AssetNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return [AgentResponse.from_domain(agent) for agent in agents]


@router.delete(
    "/{agent_id}/registry-graph",
    response_model=AgentRegistryGraphDeleteResponse,
)
async def delete_agent_registry_graph(
    tenant_id: str,
    asset_id: str,
    agent_id: str,
    delete_empty_asset: bool = False,
    delete_empty_tenant: bool = False,
    unit_of_work_factory: UnitOfWorkFactory = Depends(get_unit_of_work_factory),
) -> AgentRegistryGraphDeleteResponse:
    tenant_code = tenant_id
    asset_code = asset_id
    agent_code = agent_id
    result = await DeleteAgentRegistryGraph(unit_of_work_factory()).execute(
        DeleteAgentRegistryGraphCommand(
            tenant_code=tenant_code,
            asset_code=asset_code,
            agent_code=agent_code,
            delete_empty_asset=delete_empty_asset,
            delete_empty_tenant=delete_empty_tenant,
        )
    )
    return AgentRegistryGraphDeleteResponse.from_result(result)


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
    tenant_code = tenant_id
    asset_code = asset_id
    agent_code = agent_id
    try:
        rendered = await RenderAgentRuntimeConfig(unit_of_work_factory(), validator).execute(
            RenderAgentRuntimeConfigCommand(
                tenant_code=tenant_code,
                asset_code=asset_code,
                agent_code=agent_code,
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
