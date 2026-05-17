from __future__ import annotations

from uuid import uuid4

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
    AgentRuntimeConfigRevisionModel,
    ConfigOutboxModel,
    SourceConfigRevisionModel,
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
        "tenant_code",
        "agent_code",
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
                tenant_code=selection.tenant_code,
                asset_code=selection.asset_code,
                agent_code=selection.agent_code,
                config_revision=str(data["config_revision"]),
                issued_at=parse_issued_at(data.get("issued_at")),
                agent_runtime_payload_json=json_object(
                    data.get("agent_runtime_payload_json"),
                    field_name="agent_runtime_payload_json",
                ),
            )
        )
        return _agent_runtime_config_revision_model(revision)


class SourceConfigRevisionBackofficeView(
    AppendOnlyBackofficeModelView,
    model=SourceConfigRevisionModel,
):
    name = "Source Config Revision"
    name_plural = "Source Config Revisions"
    category = "Config Revisions"
    column_list = model_columns(
        SourceConfigRevisionModel,
        "tenant_code",
        "source_code",
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
                tenant_code=selection.tenant_code,
                asset_code=selection.asset_code,
                agent_code=selection.agent_code,
                source_code=selection.source_code,
                source_config_revision=str(data["source_config_revision"]),
                config_revision=str(data["config_revision"]),
                issued_at=parse_issued_at(data.get("issued_at")),
                source_payload_json=json_object(
                    data.get("source_payload_json"),
                    field_name="source_payload_json",
                ),
            )
        )
        return _source_config_revision_model(revision)


class ConfigOutboxBackofficeView(ReadOnlyBackofficeModelView, model=ConfigOutboxModel):
    name = "Config Outbox Record"
    name_plural = "Config Outbox Records"
    category = "Delivery"
    column_list = model_columns(
        ConfigOutboxModel,
        "status",
        "tenant_code",
        "agent_code",
        "config_revision",
        "config_scope",
        "message_type",
        "source_code",
        "attempt_count",
        "updated_at",
    )
    column_details_list = all_model_columns(ConfigOutboxModel)


def _agent_runtime_config_revision_model(
    revision: AgentRuntimeConfigRevision,
) -> AgentRuntimeConfigRevisionModel:
    return AgentRuntimeConfigRevisionModel(
        id=uuid4(),
        tenant_id=uuid4(),
        asset_id=uuid4(),
        agent_id=uuid4(),
        tenant_code=revision.tenant_code,
        asset_code=revision.asset_code,
        agent_code=revision.agent_code,
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
        tenant_id=uuid4(),
        asset_id=uuid4(),
        agent_id=uuid4(),
        source_id=uuid4(),
        agent_runtime_config_revision_id=uuid4(),
        tenant_code=revision.tenant_code,
        asset_code=revision.asset_code,
        agent_code=revision.agent_code,
        source_code=revision.source_code,
        source_config_revision=revision.source_config_revision,
        config_revision=revision.config_revision,
        status=revision.status.value,
        issued_at=revision.issued_at,
        source_payload_json=dict(revision.source_payload_json),
        created_at=revision.created_at,
    )


def _require_agent_selection(value: object | None) -> AgentSelection:
    if isinstance(value, AgentSelection):
        return value
    raise ValueError("Agent selection must come from the backoffice form")


def _require_source_selection(value: object | None) -> SourceSelection:
    if isinstance(value, SourceSelection):
        return value
    raise ValueError("Source selection must come from the backoffice form")
