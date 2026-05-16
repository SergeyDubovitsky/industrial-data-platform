from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from sqladmin import action
from sqlalchemy import select
from starlette.requests import Request
from starlette.responses import HTMLResponse

from idp_config_registry.application.use_cases.agents import (
    CreateAgent,
    CreateAgentCommand,
    DeleteAgent,
    DeleteAgentCommand,
    UpdateAgent,
    UpdateAgentCommand,
)
from idp_config_registry.application.use_cases.assets import (
    CreateAsset,
    CreateAssetCommand,
    DeleteAsset,
    DeleteAssetCommand,
    UpdateAsset,
    UpdateAssetCommand,
)
from idp_config_registry.application.use_cases.points import (
    CreatePoint,
    CreatePointCommand,
    DeletePoint,
    DeletePointCommand,
    UpdatePoint,
    UpdatePointCommand,
)
from idp_config_registry.application.use_cases.sources import (
    CreateSource,
    CreateSourceCommand,
    DeleteSource,
    DeleteSourceCommand,
    UpdateSource,
    UpdateSourceCommand,
)
from idp_config_registry.application.use_cases.tenants import (
    CreateTenant,
    CreateTenantCommand,
    DeleteTenant,
    DeleteTenantCommand,
    UpdateTenant,
    UpdateTenantCommand,
)
from idp_config_registry.domain.entities import Agent, Asset, Point, Source, Tenant
from idp_config_registry.domain.value_objects import (
    AgentStatus,
    AssetStatus,
    SignalType,
    TenantStatus,
    ValueType,
)
from idp_config_registry.infrastructure.backoffice_actions import (
    AgentRenderTarget,
    render_agent_config_action_response,
)
from idp_config_registry.infrastructure.backoffice_selectors import (
    AGENT_SELECTOR_FIELD,
    ASSET_SELECTOR_FIELD,
    SOURCE_SELECTOR_FIELD,
    TENANT_SELECTOR_FIELD,
    AgentSelection,
    AssetSelection,
    SourceSelection,
    agent_select_choices,
    asset_select_choices,
    attach_selector_value,
    bind_select_field,
    bind_string_field,
    decode_agent_selection,
    decode_asset_selection,
    decode_source_selection,
    encode_agent_selection,
    encode_asset_selection,
    encode_source_selection,
    source_select_choices,
    tenant_select_choices,
)
from idp_config_registry.infrastructure.backoffice_support import (
    BusinessBackofficeModelView,
    all_model_columns,
    default_acquisition_settings,
    default_publish_settings,
    get_current_state,
    get_request_state,
    json_object,
    model_columns,
    optional_bool,
    optional_string,
)
from idp_config_registry.infrastructure.postgres.models import (
    AgentModel,
    AssetModel,
    PointModel,
    SourceModel,
    TenantModel,
)
from idp_config_registry.infrastructure.postgres.unit_of_work import (
    PostgresUnitOfWorkFactory,
)


class ApplicationLookupBackofficeView(BusinessBackofficeModelView):
    async def get_object_for_details(self, request: Request) -> Any:
        state = get_request_state(request)
        if isinstance(state.unit_of_work_factory, PostgresUnitOfWorkFactory):
            try:
                model = await super().get_object_for_details(request)
            except ValueError:
                model = None
            if model is not None:
                return model
        return await self._get_object_from_uow(
            request.path_params["pk"],
            state.unit_of_work_factory(),
        )

    async def get_object_for_edit(self, request: Request) -> Any:
        state = get_request_state(request)
        if isinstance(state.unit_of_work_factory, PostgresUnitOfWorkFactory):
            try:
                model = await super().get_object_for_edit(request)
            except ValueError:
                model = None
            if model is not None:
                return model
        return await self._get_object_from_uow(
            request.path_params["pk"],
            state.unit_of_work_factory(),
        )

    async def get_object_for_delete(self, value: Any) -> Any:
        state = get_current_state()
        if isinstance(state.unit_of_work_factory, PostgresUnitOfWorkFactory):
            try:
                model = await super().get_object_for_delete(value)
            except ValueError:
                model = None
            if model is not None:
                return model
        return await self._get_object_from_uow(str(value), state.unit_of_work_factory())

    async def _get_object_from_uow(self, pk: str, unit_of_work: Any) -> Any:
        raise NotImplementedError


class TenantBackofficeView(ApplicationLookupBackofficeView, model=TenantModel):
    name = "Tenant"
    name_plural = "Tenants"
    category = "Registry"
    column_list = model_columns(TenantModel, "tenant_id", "name", "status", "updated_at")
    column_details_list = all_model_columns(TenantModel)
    form_columns = [
        "tenant_id",
        "name",
        "status",
    ]
    form_create_rules = [
        "tenant_id",
        "name",
    ]
    form_edit_rules = [
        "name",
        "status",
    ]

    async def scaffold_form(self, rules: list[str] | None = None) -> type:
        form = await super().scaffold_form(rules)
        if rules == self._form_create_rules:
            bind_string_field(
                form,
                field_name="tenant_id",
                label="tenant_id",
                required=True,
            )
        return form

    async def insert_model(self, request: Request, data: dict[str, object]) -> object:
        tenant = await CreateTenant(
            get_request_state(request).unit_of_work_factory()
        ).execute(
            CreateTenantCommand(
                tenant_id=str(data["tenant_id"]),
                name=str(data["name"]),
            )
        )
        return await _tenant_model_for_response(request, tenant)

    async def update_model(
        self,
        request: Request,
        pk: str,
        data: dict[str, object],
    ) -> object:
        tenant_id = await _tenant_public_identifier_value(request, pk)
        tenant = await UpdateTenant(
            get_request_state(request).unit_of_work_factory()
        ).execute(
            UpdateTenantCommand(
                tenant_id=tenant_id,
                name=str(data["name"]),
                status=TenantStatus(str(data["status"])),
            )
        )
        return await _tenant_model_for_response(request, tenant)

    async def delete_model(self, request: Request, pk: Any) -> None:
        tenant_id = await _tenant_public_identifier_value(request, str(pk))
        await DeleteTenant(get_request_state(request).unit_of_work_factory()).execute(
            DeleteTenantCommand(tenant_id=tenant_id)
        )

    async def _get_object_from_uow(self, pk: str, unit_of_work: Any) -> Any:
        async with unit_of_work as active_unit_of_work:
            tenant = await active_unit_of_work.tenants.get(pk)
        return _tenant_model(tenant) if tenant is not None else None


class AssetBackofficeView(ApplicationLookupBackofficeView, model=AssetModel):
    name = "Asset"
    name_plural = "Assets"
    category = "Registry"
    column_list = model_columns(
        AssetModel,
        "tenant_uuid",
        "asset_id",
        "name",
        "status",
        "updated_at",
    )
    column_details_list = all_model_columns(AssetModel)
    form_columns = [
        "asset_id",
        "name",
        "description",
        "status",
    ]
    form_create_rules = [
        TENANT_SELECTOR_FIELD,
        "asset_id",
        "name",
        "description",
    ]
    form_edit_rules = [
        TENANT_SELECTOR_FIELD,
        "name",
        "description",
        "status",
    ]

    async def scaffold_form(self, rules: list[str] | None = None) -> type:
        form = await super().scaffold_form(rules)
        if rules == self._form_create_rules:
            bind_string_field(
                form,
                field_name="asset_id",
                label="asset_id",
                required=True,
            )
            bind_select_field(
                form,
                field_name=TENANT_SELECTOR_FIELD,
                label="Tenant",
                choices=await tenant_select_choices(),
                coerce=str,
                required=True,
            )
        elif rules == self._form_edit_rules:
            bind_select_field(
                form,
                field_name=TENANT_SELECTOR_FIELD,
                label="Tenant",
                choices=await tenant_select_choices(),
                coerce=str,
                required=False,
                disabled=True,
            )
        return form

    async def get_object_for_edit(self, request: Request) -> Any:
        model = await super().get_object_for_edit(request)
        model = await _attach_asset_public_ids(request, model)
        return attach_selector_value(
            model,
            field_name=TENANT_SELECTOR_FIELD,
            value=_public_model_value(model, "tenant_id"),
        )

    async def insert_model(self, request: Request, data: dict[str, object]) -> object:
        asset = await CreateAsset(
            get_request_state(request).unit_of_work_factory()
        ).execute(
            CreateAssetCommand(
                tenant_id=str(data[TENANT_SELECTOR_FIELD]),
                asset_id=str(data["asset_id"]),
                name=str(data["name"]),
                description=optional_string(data.get("description")),
            )
        )
        return await _asset_model_for_response(request, asset)

    async def update_model(
        self,
        request: Request,
        pk: str,
        data: dict[str, object],
    ) -> object:
        tenant_id, asset_id = await _asset_public_identifier_values(request, pk)
        asset = await UpdateAsset(
            get_request_state(request).unit_of_work_factory()
        ).execute(
            UpdateAssetCommand(
                tenant_id=str(tenant_id),
                asset_id=str(asset_id),
                name=str(data["name"]),
                description=optional_string(data.get("description")),
                status=AssetStatus(str(data["status"])),
            )
        )
        return await _asset_model_for_response(request, asset)

    async def delete_model(self, request: Request, pk: Any) -> None:
        tenant_id, asset_id = await _asset_public_identifier_values(request, str(pk))
        await DeleteAsset(get_request_state(request).unit_of_work_factory()).execute(
            DeleteAssetCommand(
                tenant_id=str(tenant_id),
                asset_id=str(asset_id),
            )
        )

    async def _get_object_from_uow(self, pk: str, unit_of_work: Any) -> Any:
        tenant_id, asset_id = _public_identifier_values(pk, 2)
        async with unit_of_work as active_unit_of_work:
            asset = await active_unit_of_work.assets.get(str(tenant_id), str(asset_id))
        return _asset_model(asset) if asset is not None else None


class AgentBackofficeView(ApplicationLookupBackofficeView, model=AgentModel):
    name = "Agent"
    name_plural = "Agents"
    category = "Registry"
    column_list = model_columns(
        AgentModel,
        "tenant_uuid",
        "asset_uuid",
        "agent_id",
        "name",
        "status",
        "updated_at",
    )
    column_details_list = all_model_columns(AgentModel)
    form_columns = [
        "agent_id",
        "name",
        "status",
        "bootstrap_hint_json",
    ]
    form_create_rules = [
        ASSET_SELECTOR_FIELD,
        "agent_id",
        "name",
    ]
    form_edit_rules = [
        ASSET_SELECTOR_FIELD,
        "name",
        "status",
        "bootstrap_hint_json",
    ]

    @action(
        name="render_agent_config",
        label="Собрать config",
        confirmation_message=(
            "Собрать runtime/source config revision и создать записи config_outbox "
            "для выбранных агентов?"
        ),
        add_in_detail=True,
        add_in_list=True,
    )
    async def render_agent_config_action(self, request: Request) -> HTMLResponse:
        raw_pks = str(request.query_params.get("pks", ""))
        agent_targets = []
        for pk in raw_pks.split(","):
            if not pk:
                continue
            tenant_id, asset_id, agent_id = await _agent_public_identifier_values(
                request,
                pk,
            )
            agent_targets.append(
                AgentRenderTarget(
                    tenant_id=tenant_id,
                    asset_id=asset_id,
                    agent_id=agent_id,
                )
            )
        back_url = request.headers.get("referer") or str(
            request.url_for("admin:list", identity=self.identity)
        )
        return await render_agent_config_action_response(
            request,
            agent_targets=agent_targets,
            back_url=back_url,
        )

    async def scaffold_form(self, rules: list[str] | None = None) -> type:
        form = await super().scaffold_form(rules)
        if rules == self._form_create_rules:
            bind_string_field(
                form,
                field_name="agent_id",
                label="agent_id",
                required=True,
            )
            bind_select_field(
                form,
                field_name=ASSET_SELECTOR_FIELD,
                label="Asset",
                choices=await asset_select_choices(),
                coerce=decode_asset_selection,
                required=True,
            )
        elif rules == self._form_edit_rules:
            bind_select_field(
                form,
                field_name=ASSET_SELECTOR_FIELD,
                label="Asset",
                choices=await asset_select_choices(),
                coerce=decode_asset_selection,
                required=False,
                disabled=True,
            )
        return form

    async def get_object_for_edit(self, request: Request) -> Any:
        model = await super().get_object_for_edit(request)
        model = await _attach_agent_public_ids(request, model)
        return attach_selector_value(
            model,
            field_name=ASSET_SELECTOR_FIELD,
            value=encode_asset_selection(
                AssetSelection(
                    tenant_id=_public_model_value(model, "tenant_id"),
                    asset_id=_public_model_value(model, "asset_id"),
                )
            ),
        )

    async def insert_model(self, request: Request, data: dict[str, object]) -> object:
        asset_selection = _require_asset_selection(data.get(ASSET_SELECTOR_FIELD))
        agent = await CreateAgent(
            get_request_state(request).unit_of_work_factory()
        ).execute(
            CreateAgentCommand(
                tenant_id=asset_selection.tenant_id,
                asset_id=asset_selection.asset_id,
                agent_id=str(data["agent_id"]),
                name=optional_string(data.get("name")),
            )
        )
        return await _agent_model_for_response(request, agent)

    async def update_model(
        self,
        request: Request,
        pk: str,
        data: dict[str, object],
    ) -> object:
        tenant_id, asset_id, agent_id = await _agent_public_identifier_values(
            request,
            pk,
        )
        agent = await UpdateAgent(
            get_request_state(request).unit_of_work_factory()
        ).execute(
            UpdateAgentCommand(
                tenant_id=str(tenant_id),
                asset_id=str(asset_id),
                agent_id=str(agent_id),
                name=optional_string(data.get("name")),
                status=AgentStatus(str(data["status"])),
                bootstrap_hint_json=json_object(
                    data.get("bootstrap_hint_json"),
                    field_name="bootstrap_hint_json",
                ),
            )
        )
        return await _agent_model_for_response(request, agent)

    async def delete_model(self, request: Request, pk: Any) -> None:
        tenant_id, asset_id, agent_id = await _agent_public_identifier_values(
            request,
            str(pk),
        )
        await DeleteAgent(get_request_state(request).unit_of_work_factory()).execute(
            DeleteAgentCommand(
                tenant_id=str(tenant_id),
                asset_id=str(asset_id),
                agent_id=str(agent_id),
            )
        )

    async def _get_object_from_uow(self, pk: str, unit_of_work: Any) -> Any:
        tenant_id, asset_id, agent_id = _public_identifier_values(pk, 3)
        async with unit_of_work as active_unit_of_work:
            agent = await active_unit_of_work.agents.get(
                str(tenant_id),
                str(asset_id),
                str(agent_id),
            )
        return _agent_model(agent) if agent is not None else None


class SourceBackofficeView(ApplicationLookupBackofficeView, model=SourceModel):
    name = "Source"
    name_plural = "Sources"
    category = "Registry"
    column_list = model_columns(
        SourceModel,
        "tenant_uuid",
        "agent_uuid",
        "source_id",
        "source_type",
        "enabled",
        "name",
        "updated_at",
    )
    column_details_list = all_model_columns(SourceModel)
    form_columns = [
        "source_id",
        "source_type",
        "enabled",
        "name",
        "description",
        "connection_json",
        "acquisition_defaults_json",
        "publish_defaults_json",
    ]
    form_create_rules = [
        AGENT_SELECTOR_FIELD,
        "source_id",
        "source_type",
        "enabled",
        "name",
        "description",
    ]
    form_edit_rules = [
        AGENT_SELECTOR_FIELD,
        "source_type",
        "enabled",
        "name",
        "description",
        "connection_json",
        "acquisition_defaults_json",
        "publish_defaults_json",
    ]

    async def scaffold_form(self, rules: list[str] | None = None) -> type:
        form = await super().scaffold_form(rules)
        if rules == self._form_create_rules:
            bind_string_field(
                form,
                field_name="source_id",
                label="source_id",
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
        elif rules == self._form_edit_rules:
            bind_select_field(
                form,
                field_name=AGENT_SELECTOR_FIELD,
                label="Agent",
                choices=await agent_select_choices(),
                coerce=decode_agent_selection,
                required=False,
                disabled=True,
            )
        return form

    async def get_object_for_edit(self, request: Request) -> Any:
        model = await super().get_object_for_edit(request)
        model = await _attach_source_public_ids(request, model)
        return attach_selector_value(
            model,
            field_name=AGENT_SELECTOR_FIELD,
            value=_encode_agent_model_selection(model),
        )

    async def insert_model(self, request: Request, data: dict[str, object]) -> object:
        agent_selection = _require_agent_selection(data.get(AGENT_SELECTOR_FIELD))
        source = await CreateSource(
            get_request_state(request).unit_of_work_factory()
        ).execute(
            CreateSourceCommand(
                tenant_id=agent_selection.tenant_id,
                asset_id=agent_selection.asset_id,
                agent_id=agent_selection.agent_id,
                source_id=str(data["source_id"]),
                source_type=str(data["source_type"]),
                enabled=optional_bool(data.get("enabled"), default=True),
                name=optional_string(data.get("name")),
                description=optional_string(data.get("description")),
                acquisition_defaults_json=default_acquisition_settings(),
                publish_defaults_json=default_publish_settings(),
            )
        )
        return await _source_model_for_response(request, source)

    async def update_model(
        self,
        request: Request,
        pk: str,
        data: dict[str, object],
    ) -> object:
        (
            tenant_id,
            asset_id,
            agent_id,
            source_id,
        ) = await _source_public_identifier_values(
            request,
            pk,
        )
        source = await UpdateSource(
            get_request_state(request).unit_of_work_factory()
        ).execute(
            UpdateSourceCommand(
                tenant_id=str(tenant_id),
                asset_id=str(asset_id),
                agent_id=str(agent_id),
                source_id=str(source_id),
                source_type=str(data["source_type"]),
                enabled=optional_bool(data.get("enabled"), default=True),
                name=optional_string(data.get("name")),
                description=optional_string(data.get("description")),
                connection_json=json_object(
                    data.get("connection_json"),
                    field_name="connection_json",
                ),
                acquisition_defaults_json=json_object(
                    data.get("acquisition_defaults_json"),
                    field_name="acquisition_defaults_json",
                ),
                publish_defaults_json=json_object(
                    data.get("publish_defaults_json"),
                    field_name="publish_defaults_json",
                ),
            )
        )
        return await _source_model_for_response(request, source)

    async def delete_model(self, request: Request, pk: Any) -> None:
        (
            tenant_id,
            asset_id,
            agent_id,
            source_id,
        ) = await _source_public_identifier_values(
            request,
            str(pk),
        )
        await DeleteSource(get_request_state(request).unit_of_work_factory()).execute(
            DeleteSourceCommand(
                tenant_id=str(tenant_id),
                asset_id=str(asset_id),
                agent_id=str(agent_id),
                source_id=str(source_id),
            )
        )

    async def _get_object_from_uow(self, pk: str, unit_of_work: Any) -> Any:
        tenant_id, asset_id, agent_id, source_id = _public_identifier_values(pk, 4)
        async with unit_of_work as active_unit_of_work:
            source = await active_unit_of_work.sources.get(
                str(tenant_id),
                str(asset_id),
                str(agent_id),
                str(source_id),
            )
        return _source_model(source) if source is not None else None


class PointBackofficeView(ApplicationLookupBackofficeView, model=PointModel):
    name = "Point"
    name_plural = "Points"
    category = "Registry"
    column_list = model_columns(
        PointModel,
        "tenant_uuid",
        "source_uuid",
        "point_id",
        "point_key",
        "name",
        "value_type",
        "signal_type",
        "enabled",
        "updated_at",
    )
    column_details_list = all_model_columns(PointModel)
    form_columns = [
        "point_id",
        "point_key",
        "point_ref",
        "name",
        "description",
        "value_type",
        "value_model",
        "signal_type",
        "unit",
        "enabled",
        "acquisition_json",
        "publish_json",
        "tags_json",
    ]
    form_create_rules = [
        SOURCE_SELECTOR_FIELD,
        "point_id",
        "point_key",
        "point_ref",
        "name",
        "description",
        "value_type",
        "value_model",
        "signal_type",
        "unit",
        "enabled",
    ]
    form_edit_rules = [
        SOURCE_SELECTOR_FIELD,
        "point_key",
        "point_ref",
        "name",
        "description",
        "value_type",
        "value_model",
        "signal_type",
        "unit",
        "enabled",
        "acquisition_json",
        "publish_json",
        "tags_json",
    ]

    async def scaffold_form(self, rules: list[str] | None = None) -> type:
        form = await super().scaffold_form(rules)
        if rules == self._form_create_rules:
            bind_string_field(
                form,
                field_name="point_id",
                label="point_id",
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
        elif rules == self._form_edit_rules:
            bind_select_field(
                form,
                field_name=SOURCE_SELECTOR_FIELD,
                label="Source",
                choices=await source_select_choices(),
                coerce=decode_source_selection,
                required=False,
                disabled=True,
            )
        return form

    async def get_object_for_edit(self, request: Request) -> Any:
        model = await super().get_object_for_edit(request)
        model = await _attach_point_public_ids(request, model)
        return attach_selector_value(
            model,
            field_name=SOURCE_SELECTOR_FIELD,
            value=encode_source_selection(
                SourceSelection(
                    tenant_id=_public_model_value(model, "tenant_id"),
                    asset_id=_public_model_value(model, "asset_id"),
                    agent_id=_public_model_value(model, "agent_id"),
                    source_id=_public_model_value(model, "source_id"),
                )
            ),
        )

    async def insert_model(self, request: Request, data: dict[str, object]) -> object:
        source_selection = _require_source_selection(data.get(SOURCE_SELECTOR_FIELD))
        point = await CreatePoint(
            get_request_state(request).unit_of_work_factory()
        ).execute(
            CreatePointCommand(
                tenant_id=source_selection.tenant_id,
                asset_id=source_selection.asset_id,
                agent_id=source_selection.agent_id,
                source_id=source_selection.source_id,
                point_id=str(data["point_id"]),
                point_key=str(data["point_key"]),
                point_ref=str(data["point_ref"]),
                name=str(data["name"]),
                value_type=ValueType(str(data["value_type"])),
                value_model=str(data["value_model"]),
                signal_type=SignalType(str(data["signal_type"])),
                description=optional_string(data.get("description")),
                unit=optional_string(data.get("unit")),
                enabled=optional_bool(data.get("enabled"), default=True),
            )
        )
        return await _point_model_for_response(request, point)

    async def update_model(
        self,
        request: Request,
        pk: str,
        data: dict[str, object],
    ) -> object:
        tenant_id, point_id = await _point_public_identifier_values(request, pk)
        point = await UpdatePoint(
            get_request_state(request).unit_of_work_factory()
        ).execute(
            UpdatePointCommand(
                tenant_id=str(tenant_id),
                point_id=str(point_id),
                point_key=str(data["point_key"]),
                point_ref=str(data["point_ref"]),
                name=str(data["name"]),
                value_type=ValueType(str(data["value_type"])),
                value_model=str(data["value_model"]),
                signal_type=SignalType(str(data["signal_type"])),
                description=optional_string(data.get("description")),
                unit=optional_string(data.get("unit")),
                enabled=optional_bool(data.get("enabled"), default=True),
                acquisition_json=json_object(
                    data.get("acquisition_json"),
                    field_name="acquisition_json",
                ),
                publish_json=json_object(
                    data.get("publish_json"),
                    field_name="publish_json",
                ),
                tags_json=json_object(
                    data.get("tags_json"),
                    field_name="tags_json",
                ),
            )
        )
        return await _point_model_for_response(request, point)

    async def delete_model(self, request: Request, pk: Any) -> None:
        tenant_id, point_id = await _point_public_identifier_values(request, str(pk))
        await DeletePoint(get_request_state(request).unit_of_work_factory()).execute(
            DeletePointCommand(
                tenant_id=str(tenant_id),
                point_id=str(point_id),
            )
        )

    async def _get_object_from_uow(self, pk: str, unit_of_work: Any) -> Any:
        tenant_id, point_id = _public_identifier_values(pk, 2)
        async with unit_of_work as active_unit_of_work:
            point = await active_unit_of_work.points.get_by_id(
                str(tenant_id),
                str(point_id),
            )
        return _point_model(point) if point is not None else None


def _tenant_model(tenant: Tenant) -> TenantModel:
    return _attach_public_ids(
        TenantModel(
            id=uuid4(),
            tenant_id=tenant.tenant_id,
            name=tenant.name,
            status=tenant.status.value,
            created_at=tenant.created_at,
            updated_at=tenant.updated_at,
        ),
        name=tenant.name,
        tenant_id=tenant.tenant_id,
    )


def _asset_model(asset: Asset) -> AssetModel:
    return _attach_public_ids(
        AssetModel(
            id=uuid4(),
            tenant_uuid=uuid4(),
            asset_id=asset.asset_id,
            name=asset.name,
            description=asset.description,
            status=asset.status.value,
            created_at=asset.created_at,
            updated_at=asset.updated_at,
        ),
        tenant_id=asset.tenant_id,
        asset_id=asset.asset_id,
    )


def _agent_model(agent: Agent) -> AgentModel:
    return _attach_public_ids(
        AgentModel(
            id=uuid4(),
            tenant_uuid=uuid4(),
            asset_uuid=uuid4(),
            agent_id=agent.agent_id,
            name=agent.name,
            status=agent.status.value,
            bootstrap_hint_json=dict(agent.bootstrap_hint_json),
            created_at=agent.created_at,
            updated_at=agent.updated_at,
        ),
        tenant_id=agent.tenant_id,
        asset_id=agent.asset_id,
        agent_id=agent.agent_id,
    )


def _source_model(source: Source) -> SourceModel:
    return _attach_public_ids(
        SourceModel(
            id=uuid4(),
            tenant_uuid=uuid4(),
            agent_uuid=uuid4(),
            source_id=source.source_id,
            source_type=source.source_type,
            enabled=source.enabled,
            name=source.name,
            description=source.description,
            connection_json=dict(source.connection_json),
            acquisition_defaults_json=dict(source.acquisition_defaults_json),
            publish_defaults_json=dict(source.publish_defaults_json),
            created_at=source.created_at,
            updated_at=source.updated_at,
        ),
        tenant_id=source.tenant_id,
        asset_id=source.asset_id,
        agent_id=source.agent_id,
        source_id=source.source_id,
    )


def _point_model(point: Point) -> PointModel:
    return _attach_public_ids(
        PointModel(
            id=uuid4(),
            tenant_uuid=uuid4(),
            source_uuid=uuid4(),
            point_id=point.point_id,
            point_key=point.point_key,
            point_ref=point.point_ref,
            name=point.name,
            description=point.description,
            value_type=point.value_type.value,
            value_model=point.value_model,
            signal_type=point.signal_type.value,
            unit=point.unit,
            enabled=point.enabled,
            acquisition_json=dict(point.acquisition_json),
            publish_json=dict(point.publish_json),
            tags_json=dict(point.tags_json),
            created_at=point.created_at,
            updated_at=point.updated_at,
        ),
        tenant_id=point.tenant_id,
        asset_id=point.asset_id,
        agent_id=point.agent_id,
        source_id=point.source_id,
        point_id=point.point_id,
    )


async def _tenant_model_for_response(
    request: Request,
    tenant: Tenant,
) -> TenantModel:
    model = _tenant_model(tenant)
    tenant_uuid = await _tenant_uuid_by_code(request, tenant.tenant_id)
    if tenant_uuid is not None:
        model.id = tenant_uuid
    return model


async def _asset_model_for_response(
    request: Request,
    asset: Asset,
) -> AssetModel:
    model = _asset_model(asset)
    row = await _asset_internal_ids_by_codes(request, asset.tenant_id, asset.asset_id)
    if row is not None:
        model.id, model.tenant_uuid = row
    return model


async def _agent_model_for_response(
    request: Request,
    agent: Agent,
) -> AgentModel:
    model = _agent_model(agent)
    row = await _agent_internal_ids_by_codes(
        request,
        agent.tenant_id,
        agent.asset_id,
        agent.agent_id,
    )
    if row is not None:
        model.id, model.tenant_uuid, model.asset_uuid = row
    return model


async def _source_model_for_response(
    request: Request,
    source: Source,
) -> SourceModel:
    model = _source_model(source)
    row = await _source_internal_ids_by_codes(
        request,
        source.tenant_id,
        source.asset_id,
        source.agent_id,
        source.source_id,
    )
    if row is not None:
        model.id, model.tenant_uuid, model.agent_uuid = row
    return model


async def _point_model_for_response(
    request: Request,
    point: Point,
) -> PointModel:
    model = _point_model(point)
    row = await _point_internal_ids_by_codes(request, point.tenant_id, point.point_id)
    if row is not None:
        model.id, model.tenant_uuid, model.source_uuid = row
    return model


async def _attach_asset_public_ids(request: Request, model: Any) -> Any:
    if (
        model is None
        or not _is_postgres_request(request)
        or getattr(model, "_public_asset_id", None) is not None
    ):
        return model
    tenant_id, asset_id = await _asset_public_identifier_values_by_uuid(
        request,
        model.id,
    )
    return _attach_public_ids(model, tenant_id=tenant_id, asset_id=asset_id)


async def _attach_agent_public_ids(request: Request, model: Any) -> Any:
    if (
        model is None
        or not _is_postgres_request(request)
        or getattr(model, "_public_agent_id", None) is not None
    ):
        return model
    tenant_id, asset_id, agent_id = await _agent_public_identifier_values_by_uuid(
        request,
        model.id,
    )
    return _attach_public_ids(
        model,
        tenant_id=tenant_id,
        asset_id=asset_id,
        agent_id=agent_id,
    )


async def _attach_source_public_ids(request: Request, model: Any) -> Any:
    if (
        model is None
        or not _is_postgres_request(request)
        or getattr(model, "_public_source_id", None) is not None
    ):
        return model
    (
        tenant_id,
        asset_id,
        agent_id,
        source_id,
    ) = await _source_public_identifier_values_by_uuid(request, model.id)
    return _attach_public_ids(
        model,
        tenant_id=tenant_id,
        asset_id=asset_id,
        agent_id=agent_id,
        source_id=source_id,
    )


async def _attach_point_public_ids(request: Request, model: Any) -> Any:
    if (
        model is None
        or not _is_postgres_request(request)
        or getattr(model, "_public_point_id", None) is not None
    ):
        return model
    (
        tenant_id,
        asset_id,
        agent_id,
        source_id,
        point_id,
    ) = await _point_public_context_by_uuid(request, model.id)
    return _attach_public_ids(
        model,
        tenant_id=tenant_id,
        asset_id=asset_id,
        agent_id=agent_id,
        source_id=source_id,
        point_id=point_id,
    )


def _require_asset_selection(value: object | None) -> AssetSelection:
    if isinstance(value, AssetSelection):
        return value
    raise ValueError("Asset selection must come from the backoffice form")


def _require_agent_selection(value: object | None) -> AgentSelection:
    if isinstance(value, AgentSelection):
        return value
    raise ValueError("Agent selection must come from the backoffice form")


def _require_source_selection(value: object | None) -> SourceSelection:
    if isinstance(value, SourceSelection):
        return value
    raise ValueError("Source selection must come from the backoffice form")


def _encode_agent_model_selection(model: Any) -> str:
    return encode_agent_selection(
        AgentSelection(
            tenant_id=_public_model_value(model, "tenant_id"),
            asset_id=_public_model_value(model, "asset_id"),
            agent_id=_public_model_value(model, "agent_id"),
        )
    )


def _postgres_uow_factory_for_request(
    request: Request,
) -> PostgresUnitOfWorkFactory | None:
    factory = get_request_state(request).unit_of_work_factory
    return factory if isinstance(factory, PostgresUnitOfWorkFactory) else None


def _is_postgres_request(request: Request) -> bool:
    return _postgres_uow_factory_for_request(request) is not None


def _uuid_identifier(value: object) -> UUID | None:
    try:
        return UUID(str(value))
    except ValueError:
        return None


def _public_identifier_values_or_none(
    pk: str,
    expected_parts: int,
) -> tuple[str, ...] | None:
    parts = tuple(str(pk).split(";"))
    return parts if len(parts) == expected_parts else None


def _public_identifier_values(pk: str, expected_parts: int) -> tuple[str, ...]:
    parts = _public_identifier_values_or_none(pk, expected_parts)
    if parts is None:
        actual_parts = len(tuple(str(pk).split(";")))
        raise ValueError(
            f"Expected {expected_parts} public identifier parts, got {actual_parts}"
        )
    return parts


async def _tenant_public_identifier_value(request: Request, pk: str) -> str:
    pk_uuid = _uuid_identifier(pk)
    if _is_postgres_request(request) and pk_uuid is not None:
        return (await _tenant_public_identifier_values_by_uuid(request, pk_uuid))[0]
    return _public_identifier_values(pk, 1)[0]


async def _asset_public_identifier_values(
    request: Request,
    pk: str,
) -> tuple[str, str]:
    return await _public_identifier_values_for_request(
        request,
        pk,
        expected_parts=2,
        resolver=_asset_public_identifier_values_by_uuid,
    )


async def _agent_public_identifier_values(
    request: Request,
    pk: str,
) -> tuple[str, str, str]:
    return await _public_identifier_values_for_request(
        request,
        pk,
        expected_parts=3,
        resolver=_agent_public_identifier_values_by_uuid,
    )


async def _source_public_identifier_values(
    request: Request,
    pk: str,
) -> tuple[str, str, str, str]:
    return await _public_identifier_values_for_request(
        request,
        pk,
        expected_parts=4,
        resolver=_source_public_identifier_values_by_uuid,
    )


async def _point_public_identifier_values(
    request: Request,
    pk: str,
) -> tuple[str, str]:
    return await _public_identifier_values_for_request(
        request,
        pk,
        expected_parts=2,
        resolver=_point_public_identifier_values_by_uuid,
    )


async def _public_identifier_values_for_request(
    request: Request,
    pk: str,
    *,
    expected_parts: int,
    resolver: Any,
) -> tuple[str, ...]:
    parts = _public_identifier_values_or_none(pk, expected_parts)
    if parts is not None:
        return parts
    pk_uuid = _uuid_identifier(pk)
    if _is_postgres_request(request) and pk_uuid is not None:
        return await resolver(request, pk_uuid)
    return _public_identifier_values(pk, expected_parts)


async def _tenant_public_identifier_values_by_uuid(
    request: Request,
    pk: UUID,
) -> tuple[str]:
    factory = _require_postgres_uow_factory(request)
    async with factory.session_manager.session_factory() as session:
        tenant_code = await session.scalar(
            select(TenantModel.tenant_id).where(TenantModel.id == pk)
        )
    if tenant_code is None:
        raise ValueError(f"Tenant backoffice row {pk} does not exist")
    return (str(tenant_code),)


async def _asset_public_identifier_values_by_uuid(
    request: Request,
    pk: UUID,
) -> tuple[str, str]:
    factory = _require_postgres_uow_factory(request)
    async with factory.session_manager.session_factory() as session:
        result = await session.execute(
            select(TenantModel.tenant_id, AssetModel.asset_id)
            .select_from(AssetModel)
            .join(TenantModel, AssetModel.tenant_uuid == TenantModel.id)
            .where(AssetModel.id == pk)
        )
        row = result.first()
    if row is None:
        raise ValueError(f"Asset backoffice row {pk} does not exist")
    return str(row[0]), str(row[1])


async def _agent_public_identifier_values_by_uuid(
    request: Request,
    pk: UUID,
) -> tuple[str, str, str]:
    factory = _require_postgres_uow_factory(request)
    async with factory.session_manager.session_factory() as session:
        result = await session.execute(
            select(TenantModel.tenant_id, AssetModel.asset_id, AgentModel.agent_id)
            .select_from(AgentModel)
            .join(AssetModel, AgentModel.asset_uuid == AssetModel.id)
            .join(TenantModel, AgentModel.tenant_uuid == TenantModel.id)
            .where(AgentModel.id == pk)
        )
        row = result.first()
    if row is None:
        raise ValueError(f"Agent backoffice row {pk} does not exist")
    return str(row[0]), str(row[1]), str(row[2])


async def _source_public_identifier_values_by_uuid(
    request: Request,
    pk: UUID,
) -> tuple[str, str, str, str]:
    factory = _require_postgres_uow_factory(request)
    async with factory.session_manager.session_factory() as session:
        result = await session.execute(
            select(TenantModel.tenant_id, AssetModel.asset_id, AgentModel.agent_id, SourceModel.source_id)
            .select_from(SourceModel)
            .join(AgentModel, SourceModel.agent_uuid == AgentModel.id)
            .join(AssetModel, AgentModel.asset_uuid == AssetModel.id)
            .join(TenantModel, SourceModel.tenant_uuid == TenantModel.id)
            .where(SourceModel.id == pk)
        )
        row = result.first()
    if row is None:
        raise ValueError(f"Source backoffice row {pk} does not exist")
    return str(row[0]), str(row[1]), str(row[2]), str(row[3])


async def _point_public_identifier_values_by_uuid(
    request: Request,
    pk: UUID,
) -> tuple[str, str]:
    (
        tenant_code,
        _asset_code,
        _agent_code,
        _source_code,
        point_code,
    ) = await _point_public_context_by_uuid(request, pk)
    return tenant_code, point_code


async def _point_public_context_by_uuid(
    request: Request,
    pk: UUID,
) -> tuple[str, str, str, str, str]:
    factory = _require_postgres_uow_factory(request)
    async with factory.session_manager.session_factory() as session:
        result = await session.execute(
            select(
                TenantModel.tenant_id,
                AssetModel.asset_id,
                AgentModel.agent_id,
                SourceModel.source_id,
                PointModel.point_id,
            )
            .select_from(PointModel)
            .join(SourceModel, PointModel.source_uuid == SourceModel.id)
            .join(AgentModel, SourceModel.agent_uuid == AgentModel.id)
            .join(AssetModel, AgentModel.asset_uuid == AssetModel.id)
            .join(TenantModel, PointModel.tenant_uuid == TenantModel.id)
            .where(PointModel.id == pk)
        )
        row = result.first()
    if row is None:
        raise ValueError(f"Point backoffice row {pk} does not exist")
    return str(row[0]), str(row[1]), str(row[2]), str(row[3]), str(row[4])


async def _tenant_uuid_by_code(request: Request, tenant_code: str) -> UUID | None:
    factory = _postgres_uow_factory_for_request(request)
    if factory is None:
        return None
    async with factory.session_manager.session_factory() as session:
        return await session.scalar(
            select(TenantModel.id).where(TenantModel.tenant_id == tenant_code)
        )


async def _asset_internal_ids_by_codes(
    request: Request,
    tenant_code: str,
    asset_code: str,
) -> tuple[UUID, UUID] | None:
    factory = _postgres_uow_factory_for_request(request)
    if factory is None:
        return None
    async with factory.session_manager.session_factory() as session:
        result = await session.execute(
            select(AssetModel.id, AssetModel.tenant_uuid)
            .join(TenantModel, AssetModel.tenant_uuid == TenantModel.id)
            .where(TenantModel.tenant_id == tenant_code, AssetModel.asset_id == asset_code)
        )
        row = result.first()
    return (row[0], row[1]) if row is not None else None


async def _agent_internal_ids_by_codes(
    request: Request,
    tenant_code: str,
    asset_code: str,
    agent_code: str,
) -> tuple[UUID, UUID, UUID] | None:
    factory = _postgres_uow_factory_for_request(request)
    if factory is None:
        return None
    async with factory.session_manager.session_factory() as session:
        result = await session.execute(
            select(AgentModel.id, AgentModel.tenant_uuid, AgentModel.asset_uuid)
            .join(AssetModel, AgentModel.asset_uuid == AssetModel.id)
            .join(TenantModel, AgentModel.tenant_uuid == TenantModel.id)
            .where(
                TenantModel.tenant_id == tenant_code,
                AssetModel.asset_id == asset_code,
                AgentModel.agent_id == agent_code,
            )
        )
        row = result.first()
    return (row[0], row[1], row[2]) if row is not None else None


async def _source_internal_ids_by_codes(
    request: Request,
    tenant_code: str,
    asset_code: str,
    agent_code: str,
    source_code: str,
) -> tuple[UUID, UUID, UUID] | None:
    factory = _postgres_uow_factory_for_request(request)
    if factory is None:
        return None
    async with factory.session_manager.session_factory() as session:
        result = await session.execute(
            select(SourceModel.id, SourceModel.tenant_uuid, SourceModel.agent_uuid)
            .join(AgentModel, SourceModel.agent_uuid == AgentModel.id)
            .join(AssetModel, AgentModel.asset_uuid == AssetModel.id)
            .join(TenantModel, SourceModel.tenant_uuid == TenantModel.id)
            .where(
                TenantModel.tenant_id == tenant_code,
                AssetModel.asset_id == asset_code,
                AgentModel.agent_id == agent_code,
                SourceModel.source_id == source_code,
            )
        )
        row = result.first()
    return (row[0], row[1], row[2]) if row is not None else None


async def _point_internal_ids_by_codes(
    request: Request,
    tenant_code: str,
    point_code: str,
) -> tuple[UUID, UUID, UUID] | None:
    factory = _postgres_uow_factory_for_request(request)
    if factory is None:
        return None
    async with factory.session_manager.session_factory() as session:
        result = await session.execute(
            select(PointModel.id, PointModel.tenant_uuid, PointModel.source_uuid)
            .join(TenantModel, PointModel.tenant_uuid == TenantModel.id)
            .where(TenantModel.tenant_id == tenant_code, PointModel.point_id == point_code)
        )
        row = result.first()
    return (row[0], row[1], row[2]) if row is not None else None


def _require_postgres_uow_factory(request: Request) -> PostgresUnitOfWorkFactory:
    factory = _postgres_uow_factory_for_request(request)
    if factory is None:
        raise RuntimeError("Postgres unit of work factory is required")
    return factory


def _attach_public_ids(model: Any, **values: str | None) -> Any:
    for name, value in values.items():
        if value is not None:
            setattr(model, f"_public_{name}", value)
    return model


def _public_model_value(model: Any, name: str) -> str:
    public_value = getattr(model, f"_public_{name}", None)
    if public_value is not None:
        return str(public_value)
    return str(getattr(model, name))
