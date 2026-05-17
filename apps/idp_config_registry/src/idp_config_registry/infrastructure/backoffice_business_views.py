from __future__ import annotations

from typing import Any
from uuid import uuid4

from sqladmin import action
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
            return await super().get_object_for_details(request)
        return await self._get_object_from_uow(
            request.path_params["pk"],
            state.unit_of_work_factory(),
        )

    async def get_object_for_edit(self, request: Request) -> Any:
        state = get_request_state(request)
        if isinstance(state.unit_of_work_factory, PostgresUnitOfWorkFactory):
            return await super().get_object_for_edit(request)
        return await self._get_object_from_uow(
            request.path_params["pk"],
            state.unit_of_work_factory(),
        )

    async def get_object_for_delete(self, value: Any) -> Any:
        state = get_current_state()
        if isinstance(state.unit_of_work_factory, PostgresUnitOfWorkFactory):
            return await super().get_object_for_delete(value)
        return await self._get_object_from_uow(str(value), state.unit_of_work_factory())

    async def _get_object_from_uow(self, pk: str, unit_of_work: Any) -> Any:
        raise NotImplementedError


class TenantBackofficeView(ApplicationLookupBackofficeView, model=TenantModel):
    name = "Tenant"
    name_plural = "Tenants"
    category = "Registry"
    column_list = model_columns(TenantModel, "tenant_code", "name", "status", "updated_at")
    column_details_list = all_model_columns(TenantModel)
    form_columns = [
        "tenant_code",
        "name",
        "status",
    ]
    form_create_rules = [
        "tenant_code",
        "name",
    ]
    form_edit_rules = [
        "name",
        "status",
    ]

    async def insert_model(self, request: Request, data: dict[str, object]) -> object:
        tenant = await CreateTenant(get_request_state(request).unit_of_work_factory()).execute(
            CreateTenantCommand(
                tenant_code=str(data["tenant_code"]),
                name=str(data["name"]),
            )
        )
        return _tenant_model(tenant)

    async def update_model(
        self,
        request: Request,
        pk: str,
        data: dict[str, object],
    ) -> object:
        tenant = await UpdateTenant(get_request_state(request).unit_of_work_factory()).execute(
            UpdateTenantCommand(
                tenant_code=str(pk),
                name=str(data["name"]),
                status=TenantStatus(str(data["status"])),
            )
        )
        return _tenant_model(tenant)

    async def delete_model(self, request: Request, pk: Any) -> None:
        await DeleteTenant(get_request_state(request).unit_of_work_factory()).execute(
            DeleteTenantCommand(tenant_code=str(pk))
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
        "tenant_id",
        "asset_code",
        "name",
        "status",
        "updated_at",
    )
    column_details_list = all_model_columns(AssetModel)
    form_columns = [
        "asset_code",
        "name",
        "description",
        "status",
    ]
    form_create_rules = [
        TENANT_SELECTOR_FIELD,
        "asset_code",
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
        return attach_selector_value(
            model,
            field_name=TENANT_SELECTOR_FIELD,
            value=str(model.tenant_code),
        )

    async def insert_model(self, request: Request, data: dict[str, object]) -> object:
        asset = await CreateAsset(get_request_state(request).unit_of_work_factory()).execute(
            CreateAssetCommand(
                tenant_code=str(data[TENANT_SELECTOR_FIELD]),
                asset_code=str(data["asset_code"]),
                name=str(data["name"]),
                description=optional_string(data.get("description")),
            )
        )
        return _asset_model(asset)

    async def update_model(
        self,
        request: Request,
        pk: str,
        data: dict[str, object],
    ) -> object:
        tenant_code, asset_code = _decode_composite_pk(pk, 2)
        asset = await UpdateAsset(get_request_state(request).unit_of_work_factory()).execute(
            UpdateAssetCommand(
                tenant_code=str(tenant_code),
                asset_code=str(asset_code),
                name=str(data["name"]),
                description=optional_string(data.get("description")),
                status=AssetStatus(str(data["status"])),
            )
        )
        return _asset_model(asset)

    async def delete_model(self, request: Request, pk: Any) -> None:
        tenant_code, asset_code = _decode_composite_pk(str(pk), 2)
        await DeleteAsset(get_request_state(request).unit_of_work_factory()).execute(
            DeleteAssetCommand(
                tenant_code=str(tenant_code),
                asset_code=str(asset_code),
            )
        )

    async def _get_object_from_uow(self, pk: str, unit_of_work: Any) -> Any:
        tenant_code, asset_code = _decode_composite_pk(pk, 2)
        async with unit_of_work as active_unit_of_work:
            asset = await active_unit_of_work.assets.get(str(tenant_code), str(asset_code))
        return _asset_model(asset) if asset is not None else None


class AgentBackofficeView(ApplicationLookupBackofficeView, model=AgentModel):
    name = "Agent"
    name_plural = "Agents"
    category = "Registry"
    column_list = model_columns(
        AgentModel,
        "tenant_id",
        "asset_id",
        "agent_code",
        "name",
        "status",
        "updated_at",
    )
    column_details_list = all_model_columns(AgentModel)
    form_columns = [
        "agent_code",
        "name",
        "status",
        "bootstrap_hint_json",
    ]
    form_create_rules = [
        ASSET_SELECTOR_FIELD,
        "agent_code",
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
        agent_targets = [
            AgentRenderTarget(
                tenant_code=str(tenant_code),
                asset_code=str(asset_code),
                agent_code=str(agent_code),
            )
            for tenant_code, asset_code, agent_code in (
                _decode_composite_pk(pk, 3)
                for pk in raw_pks.split(",")
                if pk
            )
        ]
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
        return attach_selector_value(
            model,
            field_name=ASSET_SELECTOR_FIELD,
            value=encode_asset_selection(
                AssetSelection(
                    tenant_code=str(model.tenant_code),
                    asset_code=str(model.asset_code),
                )
            ),
        )

    async def insert_model(self, request: Request, data: dict[str, object]) -> object:
        asset_selection = _require_asset_selection(data.get(ASSET_SELECTOR_FIELD))
        agent = await CreateAgent(get_request_state(request).unit_of_work_factory()).execute(
            CreateAgentCommand(
                tenant_code=asset_selection.tenant_code,
                asset_code=asset_selection.asset_code,
                agent_code=str(data["agent_code"]),
                name=optional_string(data.get("name")),
            )
        )
        return _agent_model(agent)

    async def update_model(
        self,
        request: Request,
        pk: str,
        data: dict[str, object],
    ) -> object:
        tenant_code, asset_code, agent_code = _decode_composite_pk(pk, 3)
        agent = await UpdateAgent(get_request_state(request).unit_of_work_factory()).execute(
            UpdateAgentCommand(
                tenant_code=str(tenant_code),
                asset_code=str(asset_code),
                agent_code=str(agent_code),
                name=optional_string(data.get("name")),
                status=AgentStatus(str(data["status"])),
                bootstrap_hint_json=json_object(
                    data.get("bootstrap_hint_json"),
                    field_name="bootstrap_hint_json",
                ),
            )
        )
        return _agent_model(agent)

    async def delete_model(self, request: Request, pk: Any) -> None:
        tenant_code, asset_code, agent_code = _decode_composite_pk(str(pk), 3)
        await DeleteAgent(get_request_state(request).unit_of_work_factory()).execute(
            DeleteAgentCommand(
                tenant_code=str(tenant_code),
                asset_code=str(asset_code),
                agent_code=str(agent_code),
            )
        )

    async def _get_object_from_uow(self, pk: str, unit_of_work: Any) -> Any:
        tenant_code, asset_code, agent_code = _decode_composite_pk(pk, 3)
        async with unit_of_work as active_unit_of_work:
            agent = await active_unit_of_work.agents.get(
                str(tenant_code),
                str(asset_code),
                str(agent_code),
            )
        return _agent_model(agent) if agent is not None else None


class SourceBackofficeView(ApplicationLookupBackofficeView, model=SourceModel):
    name = "Source"
    name_plural = "Sources"
    category = "Registry"
    column_list = model_columns(
        SourceModel,
        "tenant_id",
        "agent_id",
        "source_code",
        "source_type",
        "enabled",
        "name",
        "updated_at",
    )
    column_details_list = all_model_columns(SourceModel)
    form_columns = [
        "source_code",
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
        "source_code",
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
        return attach_selector_value(
            model,
            field_name=AGENT_SELECTOR_FIELD,
            value=_encode_agent_model_selection(model),
        )

    async def insert_model(self, request: Request, data: dict[str, object]) -> object:
        agent_selection = _require_agent_selection(data.get(AGENT_SELECTOR_FIELD))
        source = await CreateSource(get_request_state(request).unit_of_work_factory()).execute(
            CreateSourceCommand(
                tenant_code=agent_selection.tenant_code,
                asset_code=agent_selection.asset_code,
                agent_code=agent_selection.agent_code,
                source_code=str(data["source_code"]),
                source_type=str(data["source_type"]),
                enabled=optional_bool(data.get("enabled"), default=True),
                name=optional_string(data.get("name")),
                description=optional_string(data.get("description")),
                acquisition_defaults_json=default_acquisition_settings(),
                publish_defaults_json=default_publish_settings(),
            )
        )
        return _source_model(source)

    async def update_model(
        self,
        request: Request,
        pk: str,
        data: dict[str, object],
    ) -> object:
        tenant_code, asset_code, agent_code, source_code = _decode_composite_pk(pk, 4)
        source = await UpdateSource(get_request_state(request).unit_of_work_factory()).execute(
            UpdateSourceCommand(
                tenant_code=str(tenant_code),
                asset_code=str(asset_code),
                agent_code=str(agent_code),
                source_code=str(source_code),
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
        return _source_model(source)

    async def delete_model(self, request: Request, pk: Any) -> None:
        tenant_code, asset_code, agent_code, source_code = _decode_composite_pk(str(pk), 4)
        await DeleteSource(get_request_state(request).unit_of_work_factory()).execute(
            DeleteSourceCommand(
                tenant_code=str(tenant_code),
                asset_code=str(asset_code),
                agent_code=str(agent_code),
                source_code=str(source_code),
            )
        )

    async def _get_object_from_uow(self, pk: str, unit_of_work: Any) -> Any:
        tenant_code, asset_code, agent_code, source_code = _decode_composite_pk(pk, 4)
        async with unit_of_work as active_unit_of_work:
            source = await active_unit_of_work.sources.get(
                str(tenant_code),
                str(asset_code),
                str(agent_code),
                str(source_code),
            )
        return _source_model(source) if source is not None else None


class PointBackofficeView(ApplicationLookupBackofficeView, model=PointModel):
    name = "Point"
    name_plural = "Points"
    category = "Registry"
    column_list = model_columns(
        PointModel,
        "tenant_id",
        "source_id",
        "point_code",
        "point_key",
        "name",
        "value_type",
        "signal_type",
        "enabled",
        "updated_at",
    )
    column_details_list = all_model_columns(PointModel)
    form_columns = [
        "point_code",
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
        "point_code",
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
        return attach_selector_value(
            model,
            field_name=SOURCE_SELECTOR_FIELD,
            value=encode_source_selection(
                SourceSelection(
                    tenant_code=str(model.tenant_code),
                    asset_code=str(model.asset_code),
                    agent_code=str(model.agent_code),
                    source_code=str(model.source_code),
                )
            ),
        )

    async def insert_model(self, request: Request, data: dict[str, object]) -> object:
        source_selection = _require_source_selection(data.get(SOURCE_SELECTOR_FIELD))
        point = await CreatePoint(get_request_state(request).unit_of_work_factory()).execute(
            CreatePointCommand(
                tenant_code=source_selection.tenant_code,
                asset_code=source_selection.asset_code,
                agent_code=source_selection.agent_code,
                source_code=source_selection.source_code,
                point_code=str(data["point_code"]),
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
        return _point_model(point)

    async def update_model(
        self,
        request: Request,
        pk: str,
        data: dict[str, object],
    ) -> object:
        tenant_code, point_code = _decode_composite_pk(pk, 2)
        point = await UpdatePoint(get_request_state(request).unit_of_work_factory()).execute(
            UpdatePointCommand(
                tenant_code=str(tenant_code),
                point_code=str(point_code),
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
        return _point_model(point)

    async def delete_model(self, request: Request, pk: Any) -> None:
        tenant_code, point_code = _decode_composite_pk(str(pk), 2)
        await DeletePoint(get_request_state(request).unit_of_work_factory()).execute(
            DeletePointCommand(
                tenant_code=str(tenant_code),
                point_code=str(point_code),
            )
        )

    async def _get_object_from_uow(self, pk: str, unit_of_work: Any) -> Any:
        tenant_code, point_code = _decode_composite_pk(pk, 2)
        async with unit_of_work as active_unit_of_work:
            point = await active_unit_of_work.points.get_by_id(
                str(tenant_code),
                str(point_code),
            )
        return _point_model(point) if point is not None else None


def _tenant_model(tenant: Tenant) -> TenantModel:
    return TenantModel(
        id=uuid4(),
        tenant_code=tenant.tenant_code,
        name=tenant.name,
        status=tenant.status.value,
        created_at=tenant.created_at,
        updated_at=tenant.updated_at,
    )


def _asset_model(asset: Asset) -> AssetModel:
    model = AssetModel(
        id=uuid4(),
        tenant_id=uuid4(),
        asset_code=asset.asset_code,
        name=asset.name,
        description=asset.description,
        status=asset.status.value,
        created_at=asset.created_at,
        updated_at=asset.updated_at,
    )
    model.tenant_code = asset.tenant_code
    model.asset_code = asset.asset_code
    return model


def _agent_model(agent: Agent) -> AgentModel:
    model = AgentModel(
        id=uuid4(),
        tenant_id=uuid4(),
        asset_id=uuid4(),
        agent_code=agent.agent_code,
        name=agent.name,
        status=agent.status.value,
        bootstrap_hint_json=dict(agent.bootstrap_hint_json),
        created_at=agent.created_at,
        updated_at=agent.updated_at,
    )
    model.tenant_code = agent.tenant_code
    model.asset_code = agent.asset_code
    model.agent_code = agent.agent_code
    return model


def _source_model(source: Source) -> SourceModel:
    model = SourceModel(
        id=uuid4(),
        tenant_id=uuid4(),
        agent_id=uuid4(),
        source_code=source.source_code,
        source_type=source.source_type,
        enabled=source.enabled,
        name=source.name,
        description=source.description,
        connection_json=dict(source.connection_json),
        acquisition_defaults_json=dict(source.acquisition_defaults_json),
        publish_defaults_json=dict(source.publish_defaults_json),
        created_at=source.created_at,
        updated_at=source.updated_at,
    )
    model.tenant_code = source.tenant_code
    model.asset_code = source.asset_code
    model.agent_code = source.agent_code
    model.source_code = source.source_code
    return model


def _point_model(point: Point) -> PointModel:
    model = PointModel(
        id=uuid4(),
        tenant_id=uuid4(),
        source_id=uuid4(),
        point_code=point.point_code,
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
    )
    model.tenant_code = point.tenant_code
    model.asset_code = point.asset_code
    model.agent_code = point.agent_code
    model.source_code = point.source_code
    model.point_code = point.point_code
    return model


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
            tenant_code=str(model.tenant_code),
            asset_code=str(model.asset_code),
            agent_code=str(model.agent_code),
        )
    )


def _decode_composite_pk(value: str, expected_parts: int) -> tuple[str, ...]:
    parts = tuple(value.split(";"))
    if len(parts) != expected_parts:
        raise ValueError(
            f"Expected {expected_parts} public code parts in backoffice object id"
        )
    return parts
