from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import select
from starlette.requests import Request
from wtforms import StringField

from idp_config_registry.application.use_cases.config_revisions import (
    CreateAgentRuntimeConfigRevision,
    CreateAgentRuntimeConfigRevisionCommand,
    CreateSourceConfigRevision,
    CreateSourceConfigRevisionCommand,
)
from idp_config_registry.domain.entities import (
    AgentRuntimeConfigRevision,
    SourceConfigRevision,
)
from idp_config_registry.infrastructure.backoffice_selectors import (
    AGENT_SELECTOR_FIELD,
    SOURCE_SELECTOR_FIELD,
    AgentSelection,
    SourceSelection,
    agent_select_choices,
    bind_select_field,
    bind_string_field,
    decode_agent_selection,
    decode_source_selection,
    source_select_choices,
)
from idp_config_registry.infrastructure.backoffice_support import (
    AppendOnlyBackofficeModelView,
    ReadOnlyBackofficeModelView,
    all_model_columns,
    get_request_state,
    json_object,
    model_columns,
    parse_issued_at,
)
from idp_config_registry.infrastructure.postgres.models import (
    AgentModel,
    AgentRuntimeConfigRevisionModel,
    AssetModel,
    ConfigOutboxModel,
    SourceConfigRevisionModel,
    SourceModel,
    TenantModel,
)
from idp_config_registry.infrastructure.postgres.unit_of_work import (
    PostgresUnitOfWorkFactory,
)


class AgentRuntimeConfigRevisionBackofficeView(
    AppendOnlyBackofficeModelView,
    model=AgentRuntimeConfigRevisionModel,
):
    name = "Agent Runtime Config Revision"
    name_plural = "Agent Runtime Config Revisions"
    category = "Config Revisions"
    column_list = model_columns(
        AgentRuntimeConfigRevisionModel,
        "tenant_uuid",
        "agent_uuid",
        "config_revision",
        "status",
        "issued_at",
        "created_at",
    )
    column_details_list = all_model_columns(AgentRuntimeConfigRevisionModel)
    form_columns = [
        "config_revision",
        "issued_at",
        "agent_runtime_payload_json",
    ]
    form_create_rules = [
        AGENT_SELECTOR_FIELD,
        "config_revision",
        "issued_at",
        "agent_runtime_payload_json",
    ]
    form_overrides = {"issued_at": StringField}

    async def scaffold_form(self, rules: list[str] | None = None) -> type:
        form = await super().scaffold_form(rules)
        if rules == self._form_create_rules:
            bind_string_field(
                form,
                field_name="config_revision",
                label="config_revision",
                required=True,
            )
            bind_select_field(
                form,
                field_name=AGENT_SELECTOR_FIELD,
                label="Agent",
                choices=await agent_select_choices(),
                coerce=decode_agent_selection,
                required=True,
            )
        return form

    async def insert_model(self, request: Request, data: dict[str, object]) -> object:
        selection = _require_agent_selection(data.get(AGENT_SELECTOR_FIELD))
        revision = await CreateAgentRuntimeConfigRevision(
            get_request_state(request).unit_of_work_factory()
        ).execute(
            CreateAgentRuntimeConfigRevisionCommand(
                tenant_id=selection.tenant_id,
                asset_id=selection.asset_id,
                agent_id=selection.agent_id,
                config_revision=str(data["config_revision"]),
                issued_at=parse_issued_at(data.get("issued_at")),
                agent_runtime_payload_json=json_object(
                    data.get("agent_runtime_payload_json"),
                    field_name="agent_runtime_payload_json",
                ),
            )
        )
        return await _agent_runtime_config_revision_model_for_response(
            request,
            revision,
        )


class SourceConfigRevisionBackofficeView(
    AppendOnlyBackofficeModelView,
    model=SourceConfigRevisionModel,
):
    name = "Source Config Revision"
    name_plural = "Source Config Revisions"
    category = "Config Revisions"
    column_list = model_columns(
        SourceConfigRevisionModel,
        "tenant_uuid",
        "source_uuid",
        "source_config_revision",
        "config_revision",
        "status",
        "issued_at",
        "created_at",
    )
    column_details_list = all_model_columns(SourceConfigRevisionModel)
    form_columns = [
        "source_config_revision",
        "config_revision",
        "issued_at",
        "source_payload_json",
    ]
    form_create_rules = [
        SOURCE_SELECTOR_FIELD,
        "source_config_revision",
        "config_revision",
        "issued_at",
        "source_payload_json",
    ]
    form_overrides = {"issued_at": StringField}

    async def scaffold_form(self, rules: list[str] | None = None) -> type:
        form = await super().scaffold_form(rules)
        if rules == self._form_create_rules:
            bind_string_field(
                form,
                field_name="source_config_revision",
                label="source_config_revision",
                required=True,
            )
            bind_select_field(
                form,
                field_name=SOURCE_SELECTOR_FIELD,
                label="Source",
                choices=await source_select_choices(),
                coerce=decode_source_selection,
                required=True,
            )
        return form

    async def insert_model(self, request: Request, data: dict[str, object]) -> object:
        selection = _require_source_selection(data.get(SOURCE_SELECTOR_FIELD))
        revision = await CreateSourceConfigRevision(
            get_request_state(request).unit_of_work_factory()
        ).execute(
            CreateSourceConfigRevisionCommand(
                tenant_id=selection.tenant_id,
                asset_id=selection.asset_id,
                agent_id=selection.agent_id,
                source_id=selection.source_id,
                source_config_revision=str(data["source_config_revision"]),
                config_revision=str(data["config_revision"]),
                issued_at=parse_issued_at(data.get("issued_at")),
                source_payload_json=json_object(
                    data.get("source_payload_json"),
                    field_name="source_payload_json",
                ),
            )
        )
        return await _source_config_revision_model_for_response(request, revision)


class ConfigOutboxBackofficeView(ReadOnlyBackofficeModelView, model=ConfigOutboxModel):
    name = "Config Outbox Record"
    name_plural = "Config Outbox Records"
    category = "Delivery"
    column_list = model_columns(
        ConfigOutboxModel,
        "status",
        "tenant_uuid",
        "agent_uuid",
        "config_revision",
        "config_scope",
        "message_type",
        "source_uuid",
        "attempt_count",
        "updated_at",
    )
    column_details_list = all_model_columns(ConfigOutboxModel)


def _agent_runtime_config_revision_model(
    revision: AgentRuntimeConfigRevision,
) -> AgentRuntimeConfigRevisionModel:
    return AgentRuntimeConfigRevisionModel(
        id=uuid4(),
        tenant_uuid=uuid4(),
        agent_uuid=uuid4(),
        config_revision=revision.config_revision,
        status=revision.status.value,
        issued_at=revision.issued_at,
        agent_runtime_payload_json=dict(revision.agent_runtime_payload_json),
        created_at=revision.created_at,
    )


def _source_config_revision_model(
    revision: SourceConfigRevision,
) -> SourceConfigRevisionModel:
    return SourceConfigRevisionModel(
        id=uuid4(),
        tenant_uuid=uuid4(),
        source_uuid=uuid4(),
        agent_runtime_config_revision_uuid=uuid4(),
        source_config_revision=revision.source_config_revision,
        config_revision=revision.config_revision,
        status=revision.status.value,
        issued_at=revision.issued_at,
        source_payload_json=dict(revision.source_payload_json),
        created_at=revision.created_at,
    )


async def _agent_runtime_config_revision_model_for_response(
    request: Request,
    revision: AgentRuntimeConfigRevision,
) -> AgentRuntimeConfigRevisionModel:
    model = _agent_runtime_config_revision_model(revision)
    row = await _agent_runtime_config_revision_internal_ids_by_codes(
        request,
        revision.tenant_id,
        revision.asset_id,
        revision.agent_id,
        revision.config_revision,
    )
    if row is not None:
        model.id, model.tenant_uuid, model.agent_uuid = row
    return model


async def _source_config_revision_model_for_response(
    request: Request,
    revision: SourceConfigRevision,
) -> SourceConfigRevisionModel:
    model = _source_config_revision_model(revision)
    row = await _source_config_revision_internal_ids_by_codes(
        request,
        revision.tenant_id,
        revision.asset_id,
        revision.agent_id,
        revision.source_id,
        revision.source_config_revision,
        revision.config_revision,
    )
    if row is not None:
        (
            model.id,
            model.tenant_uuid,
            model.source_uuid,
            model.agent_runtime_config_revision_uuid,
        ) = row
    return model


async def _agent_runtime_config_revision_internal_ids_by_codes(
    request: Request,
    tenant_code: str,
    asset_code: str,
    agent_code: str,
    config_revision_code: str,
) -> tuple[UUID, UUID, UUID] | None:
    factory = _postgres_uow_factory_for_request(request)
    if factory is None:
        return None
    async with factory.session_manager.session_factory() as session:
        result = await session.execute(
            select(
                AgentRuntimeConfigRevisionModel.id,
                AgentRuntimeConfigRevisionModel.tenant_uuid,
                AgentRuntimeConfigRevisionModel.agent_uuid,
            )
            .join(AgentModel, AgentRuntimeConfigRevisionModel.agent_uuid == AgentModel.id)
            .join(AssetModel, AgentModel.asset_uuid == AssetModel.id)
            .join(TenantModel, AgentRuntimeConfigRevisionModel.tenant_uuid == TenantModel.id)
            .where(
                TenantModel.tenant_id == tenant_code,
                AssetModel.asset_id == asset_code,
                AgentModel.agent_id == agent_code,
                AgentRuntimeConfigRevisionModel.config_revision == config_revision_code,
            )
        )
        row = result.first()
    return (row[0], row[1], row[2]) if row is not None else None


async def _source_config_revision_internal_ids_by_codes(
    request: Request,
    tenant_code: str,
    asset_code: str,
    agent_code: str,
    source_code: str,
    source_config_revision_code: str,
    config_revision: str,
) -> tuple[UUID, UUID, UUID, UUID] | None:
    factory = _postgres_uow_factory_for_request(request)
    if factory is None:
        return None
    async with factory.session_manager.session_factory() as session:
        result = await session.execute(
            select(
                SourceConfigRevisionModel.id,
                SourceConfigRevisionModel.tenant_uuid,
                SourceConfigRevisionModel.source_uuid,
                SourceConfigRevisionModel.agent_runtime_config_revision_uuid,
            )
            .join(SourceModel, SourceConfigRevisionModel.source_uuid == SourceModel.id)
            .join(AgentModel, SourceModel.agent_uuid == AgentModel.id)
            .join(AssetModel, AgentModel.asset_uuid == AssetModel.id)
            .join(TenantModel, SourceConfigRevisionModel.tenant_uuid == TenantModel.id)
            .where(
                TenantModel.tenant_id == tenant_code,
                AssetModel.asset_id == asset_code,
                AgentModel.agent_id == agent_code,
                SourceModel.source_id == source_code,
                SourceConfigRevisionModel.source_config_revision == source_config_revision_code,
                SourceConfigRevisionModel.config_revision == config_revision,
            )
        )
        row = result.first()
    return (row[0], row[1], row[2], row[3]) if row is not None else None


def _postgres_uow_factory_for_request(
    request: Request,
) -> PostgresUnitOfWorkFactory | None:
    factory = get_request_state(request).unit_of_work_factory
    return factory if isinstance(factory, PostgresUnitOfWorkFactory) else None


def _require_agent_selection(value: object | None) -> AgentSelection:
    if isinstance(value, AgentSelection):
        return value
    raise ValueError("Agent selection must come from the backoffice form")


def _require_source_selection(value: object | None) -> SourceSelection:
    if isinstance(value, SourceSelection):
        return value
    raise ValueError("Source selection must come from the backoffice form")
