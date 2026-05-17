from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from idp_config_registry.application.use_cases.agents import (
    CreateAgent,
    CreateAgentCommand,
)
from idp_config_registry.application.use_cases.assets import (
    CreateAsset,
    CreateAssetCommand,
)
from idp_config_registry.application.use_cases.config_revisions import (
    CreateAgentRuntimeConfigRevision,
    CreateAgentRuntimeConfigRevisionCommand,
)
from idp_config_registry.application.use_cases.points import (
    CreatePoint,
    CreatePointCommand,
)
from idp_config_registry.application.use_cases.sources import (
    CreateSource,
    CreateSourceCommand,
)
from idp_config_registry.application.use_cases.tenants import (
    CreateTenant,
    CreateTenantCommand,
)
from idp_config_registry.domain.value_objects import SignalType, ValueType
from idp_config_registry.infrastructure.backoffice import (
    BACKOFFICE_CUSTOM_VIEWS,
    BACKOFFICE_VIEWS,
    AgentBackofficeView,
    AgentRuntimeConfigRevisionBackofficeView,
    AssetBackofficeView,
    ConfigOutboxActionsBackofficeView,
    ConfigOutboxBackofficeView,
    PointBackofficeView,
    SourceBackofficeView,
    SourceConfigRevisionBackofficeView,
    TenantBackofficeView,
)
from idp_config_registry.infrastructure.backoffice_actions import (
    render_agent_config_for_agent,
)
from idp_config_registry.infrastructure.backoffice_selectors import (
    AGENT_SELECTOR_FIELD,
    ASSET_SELECTOR_FIELD,
    SOURCE_SELECTOR_FIELD,
    TENANT_SELECTOR_FIELD,
    AgentSelection,
    AssetSelection,
    SourceSelection,
    encode_agent_selection,
    encode_asset_selection,
    encode_source_selection,
)
from idp_config_registry.infrastructure.memory.unit_of_work import (
    InMemoryUnitOfWorkFactory,
)
from idp_config_registry.infrastructure.postgres.models import (
    AgentModel,
    AgentRuntimeConfigRevisionModel,
    AssetModel,
    ConfigOutboxModel,
    PointModel,
    SourceConfigRevisionModel,
    SourceModel,
    TenantModel,
)
from idp_config_registry.main import create_app
from idp_config_registry.settings import ConfigRegistrySettings

CONFIG_REGISTRY_SRC = Path(__file__).resolve().parents[1] / "src" / "idp_config_registry"

LIST_VIEW_COLUMNS: tuple[tuple[type[object], type[object], tuple[str, ...]], ...] = (
    (TenantBackofficeView, TenantModel, ("tenant_code", "name", "status", "updated_at")),
    (
        AssetBackofficeView,
        AssetModel,
        ("tenant_id", "asset_code", "name", "status", "updated_at"),
    ),
    (
        AgentBackofficeView,
        AgentModel,
        ("tenant_id", "asset_id", "agent_code", "name", "status", "updated_at"),
    ),
    (
        SourceBackofficeView,
        SourceModel,
        (
            "tenant_id",
            "agent_id",
            "source_code",
            "source_type",
            "enabled",
            "name",
            "updated_at",
        ),
    ),
    (
        PointBackofficeView,
        PointModel,
        (
            "tenant_id",
            "source_id",
            "point_code",
            "point_key",
            "name",
            "value_type",
            "signal_type",
            "enabled",
            "updated_at",
        ),
    ),
    (
        AgentRuntimeConfigRevisionBackofficeView,
        AgentRuntimeConfigRevisionModel,
        ("tenant_code", "agent_code", "config_revision", "status", "issued_at", "created_at"),
    ),
    (
        SourceConfigRevisionBackofficeView,
        SourceConfigRevisionModel,
        (
            "tenant_code",
            "source_code",
            "source_config_revision",
            "config_revision",
            "status",
            "issued_at",
            "created_at",
        ),
    ),
    (
        ConfigOutboxBackofficeView,
        ConfigOutboxModel,
        (
            "status",
            "tenant_code",
            "agent_code",
            "config_revision",
            "config_scope",
            "message_type",
            "source_code",
            "attempt_count",
            "updated_at",
        ),
    ),
)

BUSINESS_VIEWS: tuple[type[object], ...] = (
    TenantBackofficeView,
    AssetBackofficeView,
    AgentBackofficeView,
    SourceBackofficeView,
    PointBackofficeView,
)


def test_backoffice_mounts_in_internal_mode_with_postgres_uow() -> None:
    app = create_app(settings=_settings(internal_mode=True))

    with TestClient(app) as client:
        assert client.app.state.backoffice_enabled is True
        assert _has_route_prefix(client.app, "/backoffice")


def test_backoffice_is_not_mounted_outside_internal_mode() -> None:
    app = create_app(settings=_settings(internal_mode=False))

    with TestClient(app) as client:
        assert client.app.state.backoffice_enabled is False
        assert not _has_route_prefix(client.app, "/backoffice")


def test_backoffice_is_not_mounted_without_postgres_uow() -> None:
    app = create_app(settings=ConfigRegistrySettings(internal_mode=True))

    with TestClient(app) as client:
        assert client.app.state.backoffice_enabled is False
        assert not _has_route_prefix(client.app, "/backoffice")


def test_backoffice_business_views_use_application_backed_crud() -> None:
    for view in BUSINESS_VIEWS:
        assert view.can_create is True
        assert view.can_edit is True
        assert view.can_delete is True
        assert view.can_view_details is True
        assert view.can_export is True


def test_backoffice_append_only_and_action_driven_views_have_explicit_capabilities() -> None:
    assert AgentRuntimeConfigRevisionBackofficeView.can_create is True
    assert AgentRuntimeConfigRevisionBackofficeView.can_edit is False
    assert AgentRuntimeConfigRevisionBackofficeView.can_delete is False

    assert SourceConfigRevisionBackofficeView.can_create is True
    assert SourceConfigRevisionBackofficeView.can_edit is False
    assert SourceConfigRevisionBackofficeView.can_delete is False

    assert ConfigOutboxBackofficeView.can_create is False
    assert ConfigOutboxBackofficeView.can_edit is False
    assert ConfigOutboxBackofficeView.can_delete is False


def test_backoffice_registers_custom_operator_views() -> None:
    assert ConfigOutboxActionsBackofficeView in BACKOFFICE_CUSTOM_VIEWS
    assert len(BACKOFFICE_CUSTOM_VIEWS) == 1


def test_backoffice_view_registry_contains_business_and_technical_views() -> None:
    assert BACKOFFICE_VIEWS
    assert TenantBackofficeView in BACKOFFICE_VIEWS
    assert AgentRuntimeConfigRevisionBackofficeView in BACKOFFICE_VIEWS
    assert ConfigOutboxBackofficeView in BACKOFFICE_VIEWS


def test_backoffice_bulk_action_affordances_follow_view_capabilities() -> None:
    app = create_app(settings=_settings(internal_mode=True))
    agent_view = next(
        view for view in app.state.backoffice.views if isinstance(view, AgentBackofficeView)
    )
    runtime_view = next(
        view
        for view in app.state.backoffice.views
        if isinstance(view, AgentRuntimeConfigRevisionBackofficeView)
    )
    source_view = next(
        view
        for view in app.state.backoffice.views
        if isinstance(view, SourceConfigRevisionBackofficeView)
    )

    assert agent_view.show_bulk_actions is True
    assert runtime_view.show_bulk_actions is False
    assert source_view.show_bulk_actions is False


def test_backoffice_tenant_create_form_hides_system_fields() -> None:
    app = create_app(settings=_settings(internal_mode=True))
    app.state.unit_of_work_factory = InMemoryUnitOfWorkFactory()

    with TestClient(app) as client:
        response = client.get("/backoffice/tenant-model/create")

    assert response.status_code == 200
    assert 'name="tenant_code"' in response.text
    assert 'name="name"' in response.text
    assert 'name="status"' not in response.text
    assert 'name="created_at"' not in response.text
    assert 'name="updated_at"' not in response.text


@pytest.mark.asyncio
async def test_backoffice_asset_create_form_uses_tenant_selector() -> None:
    app = create_app(settings=_settings(internal_mode=True))
    app.state.unit_of_work_factory = InMemoryUnitOfWorkFactory()
    await _seed_registry_tree(app)

    with TestClient(app) as client:
        response = client.get("/backoffice/asset-model/create")

    assert response.status_code == 200
    assert f'name="{TENANT_SELECTOR_FIELD}"' in response.text
    assert 'name="tenant_id"' not in response.text
    assert 'name="asset_code"' in response.text
    assert "Tenant Backoffice (tenant-backoffice)" in response.text


@pytest.mark.asyncio
async def test_backoffice_agent_create_form_uses_asset_selector() -> None:
    app = create_app(settings=_settings(internal_mode=True))
    app.state.unit_of_work_factory = InMemoryUnitOfWorkFactory()
    await _seed_registry_tree(app)

    with TestClient(app) as client:
        response = client.get("/backoffice/agent-model/create")

    assert response.status_code == 200
    assert f'name="{ASSET_SELECTOR_FIELD}"' in response.text
    assert 'name="tenant_id"' not in response.text
    assert 'name="asset_id"' not in response.text
    assert 'name="agent_code"' in response.text
    assert (
        "Tenant Backoffice (tenant-backoffice) / Asset Backoffice (asset-backoffice)"
    ) in response.text


@pytest.mark.asyncio
async def test_backoffice_source_create_form_uses_agent_selector() -> None:
    app = create_app(settings=_settings(internal_mode=True))
    app.state.unit_of_work_factory = InMemoryUnitOfWorkFactory()
    await _seed_registry_tree(app)

    with TestClient(app) as client:
        response = client.get("/backoffice/source-model/create")

    assert response.status_code == 200
    assert f'name="{AGENT_SELECTOR_FIELD}"' in response.text
    assert 'name="tenant_id"' not in response.text
    assert 'name="asset_id"' not in response.text
    assert 'name="agent_id"' not in response.text
    assert 'name="source_code"' in response.text
    assert 'name="connection_json"' not in response.text


@pytest.mark.asyncio
async def test_backoffice_point_create_form_uses_source_selector() -> None:
    app = create_app(settings=_settings(internal_mode=True))
    app.state.unit_of_work_factory = InMemoryUnitOfWorkFactory()
    await _seed_registry_tree(app)

    with TestClient(app) as client:
        response = client.get("/backoffice/point-model/create")

    assert response.status_code == 200
    assert f'name="{SOURCE_SELECTOR_FIELD}"' in response.text
    assert 'name="tenant_id"' not in response.text
    assert 'name="asset_id"' not in response.text
    assert 'name="agent_id"' not in response.text
    assert 'name="source_id"' not in response.text
    assert 'name="point_code"' in response.text
    assert 'name="acquisition_json"' not in response.text


@pytest.mark.asyncio
async def test_agent_runtime_config_revision_create_form_uses_agent_selector() -> None:
    app = create_app(settings=_settings(internal_mode=True))
    app.state.unit_of_work_factory = InMemoryUnitOfWorkFactory()
    await _seed_registry_tree(app)

    with TestClient(app) as client:
        response = client.get("/backoffice/agent-runtime-config-revision-model/create")

    assert response.status_code == 200
    assert f'name="{AGENT_SELECTOR_FIELD}"' in response.text
    assert 'name="agent_id"' not in response.text
    assert 'name="config_revision"' in response.text
    assert 'name="issued_at"' in response.text
    assert 'name="agent_runtime_payload_json"' in response.text
    assert 'name="status"' not in response.text


@pytest.mark.asyncio
async def test_source_config_revision_create_form_uses_source_selector() -> None:
    app = create_app(settings=_settings(internal_mode=True))
    app.state.unit_of_work_factory = InMemoryUnitOfWorkFactory()
    await _seed_registry_tree(app)

    with TestClient(app) as client:
        response = client.get("/backoffice/source-config-revision-model/create")

    assert response.status_code == 200
    assert f'name="{SOURCE_SELECTOR_FIELD}"' in response.text
    assert 'name="source_id"' not in response.text
    assert 'name="source_config_revision"' in response.text
    assert 'name="source_payload_json"' in response.text
    assert 'name="status"' not in response.text


@pytest.mark.asyncio
async def test_backoffice_agent_edit_form_keeps_asset_selector_in_ui() -> None:
    app = create_app(settings=_settings(internal_mode=True))
    app.state.unit_of_work_factory = InMemoryUnitOfWorkFactory()
    await _seed_registry_tree(app)

    with TestClient(app) as client:
        response = client.get(
            "/backoffice/agent-model/edit/tenant-backoffice;asset-backoffice;agent-backoffice"
        )

    assert response.status_code == 200
    assert f'name="{ASSET_SELECTOR_FIELD}"' in response.text
    assert 'disabled' in response.text
    assert 'name="bootstrap_hint_json"' in response.text


@pytest.mark.asyncio
async def test_backoffice_source_edit_form_keeps_agent_selector_in_ui() -> None:
    app = create_app(settings=_settings(internal_mode=True))
    app.state.unit_of_work_factory = InMemoryUnitOfWorkFactory()
    await _seed_registry_tree(app)

    with TestClient(app) as client:
        response = client.get(
            "/backoffice/source-model/edit/"
            "tenant-backoffice;asset-backoffice;agent-backoffice;source-backoffice"
        )

    assert response.status_code == 200
    assert f'name="{AGENT_SELECTOR_FIELD}"' in response.text
    assert 'disabled' in response.text
    assert 'name="connection_json"' in response.text


@pytest.mark.asyncio
async def test_backoffice_point_edit_form_keeps_source_selector_in_ui() -> None:
    app = create_app(settings=_settings(internal_mode=True))
    app.state.unit_of_work_factory = InMemoryUnitOfWorkFactory()
    await _seed_registry_tree(app)

    with TestClient(app) as client:
        response = client.get(
            "/backoffice/point-model/edit/tenant-backoffice;point-backoffice"
        )

    assert response.status_code == 200
    assert f'name="{SOURCE_SELECTOR_FIELD}"' in response.text
    assert 'disabled' in response.text
    assert 'name="acquisition_json"' in response.text


def test_backoffice_can_create_tenant_via_mounted_form() -> None:
    app = create_app(settings=_settings(internal_mode=True))
    app.state.unit_of_work_factory = InMemoryUnitOfWorkFactory()

    with TestClient(app) as client:
        response = client.post(
            "/backoffice/tenant-model/create",
            data={
                "tenant_code": "tenant-ui",
                "name": "Tenant UI",
                "save": "Save",
            },
            follow_redirects=False,
        )
        tenants = client.get("/tenants").json()

    assert response.status_code == 302
    assert any(tenant["tenant_id"] == "tenant-ui" for tenant in tenants)


@pytest.mark.asyncio
async def test_backoffice_can_create_asset_via_mounted_form() -> None:
    app = create_app(settings=_settings(internal_mode=True))
    app.state.unit_of_work_factory = InMemoryUnitOfWorkFactory()
    await _seed_registry_tree(app)

    with TestClient(app) as client:
        response = client.post(
            "/backoffice/asset-model/create",
            data={
                TENANT_SELECTOR_FIELD: "tenant-backoffice",
                "asset_code": "asset-ui",
                "name": "Asset UI",
                "description": "Created from mounted backoffice form",
                "save": "Save",
            },
            follow_redirects=False,
        )
        assets = client.get("/tenants/tenant-backoffice/assets").json()

    assert response.status_code == 302
    assert any(asset["asset_id"] == "asset-ui" for asset in assets)


@pytest.mark.asyncio
async def test_backoffice_can_create_agent_via_mounted_form() -> None:
    app = create_app(settings=_settings(internal_mode=True))
    app.state.unit_of_work_factory = InMemoryUnitOfWorkFactory()
    await _seed_registry_tree(app)

    with TestClient(app) as client:
        response = client.post(
            "/backoffice/agent-model/create",
            data={
                ASSET_SELECTOR_FIELD: encode_asset_selection(
                    AssetSelection(
                        tenant_code="tenant-backoffice",
                        asset_code="asset-backoffice",
                    )
                ),
                "agent_code": "agent-ui",
                "name": "Agent UI",
                "save": "Save",
            },
            follow_redirects=False,
        )
        agents = client.get(
            "/tenants/tenant-backoffice/assets/asset-backoffice/agents"
        ).json()

    assert response.status_code == 302
    assert any(agent["agent_id"] == "agent-ui" for agent in agents)


@pytest.mark.asyncio
async def test_backoffice_can_create_source_via_mounted_form() -> None:
    app = create_app(settings=_settings(internal_mode=True))
    app.state.unit_of_work_factory = InMemoryUnitOfWorkFactory()
    await _seed_registry_tree(app)

    with TestClient(app) as client:
        response = client.post(
            "/backoffice/source-model/create",
            data={
                AGENT_SELECTOR_FIELD: encode_agent_selection(
                    AgentSelection(
                        tenant_code="tenant-backoffice",
                        asset_code="asset-backoffice",
                        agent_code="agent-backoffice",
                    )
                ),
                "source_code": "source-ui",
                "source_type": "knx",
                "enabled": "y",
                "name": "Source UI",
                "description": "Created from mounted backoffice form",
                "save": "Save",
            },
            follow_redirects=False,
        )
        sources = client.get(
            "/tenants/tenant-backoffice/assets/asset-backoffice"
            "/agents/agent-backoffice/sources"
        ).json()

    assert response.status_code == 302
    assert any(source["source_id"] == "source-ui" for source in sources)


@pytest.mark.asyncio
async def test_backoffice_can_create_point_via_mounted_form() -> None:
    app = create_app(settings=_settings(internal_mode=True))
    app.state.unit_of_work_factory = InMemoryUnitOfWorkFactory()
    await _seed_registry_tree(app)

    with TestClient(app) as client:
        response = client.post(
            "/backoffice/point-model/create",
            data={
                SOURCE_SELECTOR_FIELD: encode_source_selection(
                    SourceSelection(
                        tenant_code="tenant-backoffice",
                        asset_code="asset-backoffice",
                        agent_code="agent-backoffice",
                        source_code="source-backoffice",
                    )
                ),
                "point_code": "point-ui",
                "point_key": "2%2F3%2F4",
                "point_ref": "2/3/4",
                "name": "Point UI",
                "description": "Created from mounted backoffice form",
                "value_type": "number",
                "value_model": "knx.dpt.9.001",
                "signal_type": "sensor",
                "unit": "C",
                "enabled": "y",
                "save": "Save",
            },
            follow_redirects=False,
        )
        points = client.get(
            "/tenants/tenant-backoffice/assets/asset-backoffice"
            "/agents/agent-backoffice/sources/source-backoffice/points"
        ).json()

    assert response.status_code == 302
    assert any(point["point_id"] == "point-ui" for point in points)


@pytest.mark.asyncio
async def test_backoffice_can_update_tenant_via_mounted_form() -> None:
    app = create_app(settings=_settings(internal_mode=True))
    app.state.unit_of_work_factory = InMemoryUnitOfWorkFactory()
    await _seed_registry_tree(app)

    with TestClient(app) as client:
        response = client.post(
            "/backoffice/tenant-model/edit/tenant-backoffice",
            data={
                "name": "Tenant Backoffice Updated",
                "status": "disabled",
                "save": "Save",
            },
            follow_redirects=False,
        )
        tenants = client.get("/tenants").json()

    assert response.status_code == 302
    assert any(
        tenant["tenant_id"] == "tenant-backoffice"
        and tenant["name"] == "Tenant Backoffice Updated"
        for tenant in tenants
    )


@pytest.mark.asyncio
async def test_backoffice_can_update_asset_via_mounted_form() -> None:
    app = create_app(settings=_settings(internal_mode=True))
    app.state.unit_of_work_factory = InMemoryUnitOfWorkFactory()
    await _seed_registry_tree(app)

    with TestClient(app) as client:
        response = client.post(
            "/backoffice/asset-model/edit/tenant-backoffice;asset-backoffice",
            data={
                "name": "Asset Backoffice Updated",
                "description": "Updated from mounted edit form",
                "status": "disabled",
                "save": "Save",
            },
            follow_redirects=False,
        )
        assets = client.get("/tenants/tenant-backoffice/assets").json()

    assert response.status_code == 302
    assert any(
        asset["asset_id"] == "asset-backoffice"
        and asset["name"] == "Asset Backoffice Updated"
        for asset in assets
    )


@pytest.mark.asyncio
async def test_backoffice_can_update_agent_via_mounted_form() -> None:
    app = create_app(settings=_settings(internal_mode=True))
    app.state.unit_of_work_factory = InMemoryUnitOfWorkFactory()
    await _seed_registry_tree(app)

    with TestClient(app) as client:
        response = client.post(
            "/backoffice/agent-model/edit/"
            "tenant-backoffice;asset-backoffice;agent-backoffice",
            data={
                "name": "Agent Backoffice Updated",
                "status": "disabled",
                "bootstrap_hint_json": '{"mode":"manual"}',
                "save": "Save",
            },
            follow_redirects=False,
        )
        agents = client.get(
            "/tenants/tenant-backoffice/assets/asset-backoffice/agents"
        ).json()

    assert response.status_code == 302
    assert any(
        agent["agent_id"] == "agent-backoffice"
        and agent["name"] == "Agent Backoffice Updated"
        for agent in agents
    )


@pytest.mark.asyncio
async def test_backoffice_can_update_source_via_mounted_form() -> None:
    app = create_app(settings=_settings(internal_mode=True))
    app.state.unit_of_work_factory = InMemoryUnitOfWorkFactory()
    await _seed_registry_tree(app)

    with TestClient(app) as client:
        response = client.post(
            "/backoffice/source-model/edit/"
            "tenant-backoffice;asset-backoffice;agent-backoffice;source-backoffice",
            data={
                "source_type": "knx",
                "enabled": "off",
                "name": "Source Backoffice Updated",
                "description": "Updated from mounted edit form",
                "connection_json": '{"host":"127.0.0.1"}',
                "acquisition_defaults_json": '{"listen": true, "read_on_start": true, "periodic_interval_seconds": 60}',
                "publish_defaults_json": '{"enabled": true, "change_threshold": 0.5}',
                "save": "Save",
            },
            follow_redirects=False,
        )
        sources = client.get(
            "/tenants/tenant-backoffice/assets/asset-backoffice"
            "/agents/agent-backoffice/sources"
        ).json()

    assert response.status_code == 302
    assert any(
        source["source_id"] == "source-backoffice"
        and source["name"] == "Source Backoffice Updated"
        for source in sources
    )


@pytest.mark.asyncio
async def test_backoffice_can_update_point_via_mounted_form() -> None:
    app = create_app(settings=_settings(internal_mode=True))
    app.state.unit_of_work_factory = InMemoryUnitOfWorkFactory()
    await _seed_registry_tree(app)

    with TestClient(app) as client:
        response = client.post(
            "/backoffice/point-model/edit/tenant-backoffice;point-backoffice",
            data={
                "point_key": "1%2F2%2F4",
                "point_ref": "1/2/4",
                "name": "Point Backoffice Updated",
                "description": "Updated from mounted edit form",
                "value_type": "number",
                "value_model": "knx.dpt.9.001",
                "signal_type": "sensor",
                "unit": "F",
                "enabled": "off",
                "acquisition_json": '{"debounce_ms": 500}',
                "publish_json": '{"enabled": true}',
                "tags_json": '{"room": "lab"}',
                "save": "Save",
            },
            follow_redirects=False,
        )
        points = client.get(
            "/tenants/tenant-backoffice/assets/asset-backoffice"
            "/agents/agent-backoffice/sources/source-backoffice/points"
        ).json()

    assert response.status_code == 302
    assert any(
        point["point_id"] == "point-backoffice"
        and point["name"] == "Point Backoffice Updated"
        and point["point_key"] == "1%2F2%2F4"
        for point in points
    )


@pytest.mark.asyncio
async def test_backoffice_can_delete_tenant_via_mounted_delete_route() -> None:
    app = create_app(settings=_settings(internal_mode=True))
    app.state.unit_of_work_factory = InMemoryUnitOfWorkFactory()
    await CreateTenant(app.state.unit_of_work_factory()).execute(
        CreateTenantCommand(tenant_code="tenant-delete", name="Tenant Delete")
    )

    with TestClient(app) as client:
        response = client.request(
            "DELETE",
            "/backoffice/tenant-model/delete?pks=tenant-delete",
            headers={"referer": "http://testserver/backoffice/tenant-model/list"},
        )
        tenants = client.get("/tenants").json()

    assert response.status_code == 200
    assert not any(tenant["tenant_id"] == "tenant-delete" for tenant in tenants)


@pytest.mark.asyncio
async def test_backoffice_can_delete_asset_via_mounted_delete_route() -> None:
    app = create_app(settings=_settings(internal_mode=True))
    app.state.unit_of_work_factory = InMemoryUnitOfWorkFactory()
    await _seed_registry_tree(app)
    await CreateAsset(app.state.unit_of_work_factory()).execute(
        CreateAssetCommand(
            tenant_code="tenant-backoffice",
            asset_code="asset-delete",
            name="Asset Delete",
        )
    )

    with TestClient(app) as client:
        response = client.request(
            "DELETE",
            "/backoffice/asset-model/delete?pks=tenant-backoffice;asset-delete",
            headers={"referer": "http://testserver/backoffice/asset-model/list"},
        )
        assets = client.get("/tenants/tenant-backoffice/assets").json()

    assert response.status_code == 200
    assert not any(asset["asset_id"] == "asset-delete" for asset in assets)


@pytest.mark.asyncio
async def test_backoffice_can_delete_agent_via_mounted_delete_route() -> None:
    app = create_app(settings=_settings(internal_mode=True))
    app.state.unit_of_work_factory = InMemoryUnitOfWorkFactory()
    await _seed_registry_tree(app)
    await CreateAgent(app.state.unit_of_work_factory()).execute(
        CreateAgentCommand(
            tenant_code="tenant-backoffice",
            asset_code="asset-backoffice",
            agent_code="agent-delete",
        )
    )

    with TestClient(app) as client:
        response = client.request(
            "DELETE",
            "/backoffice/agent-model/delete?"
            "pks=tenant-backoffice;asset-backoffice;agent-delete",
            headers={"referer": "http://testserver/backoffice/agent-model/list"},
        )
        agents = client.get(
            "/tenants/tenant-backoffice/assets/asset-backoffice/agents"
        ).json()

    assert response.status_code == 200
    assert not any(agent["agent_id"] == "agent-delete" for agent in agents)


@pytest.mark.asyncio
async def test_backoffice_can_delete_source_via_mounted_delete_route() -> None:
    app = create_app(settings=_settings(internal_mode=True))
    app.state.unit_of_work_factory = InMemoryUnitOfWorkFactory()
    await _seed_registry_tree(app)
    await CreateSource(app.state.unit_of_work_factory()).execute(
        CreateSourceCommand(
            tenant_code="tenant-backoffice",
            asset_code="asset-backoffice",
            agent_code="agent-backoffice",
            source_code="source-delete",
            source_type="knx",
            acquisition_defaults_json={
                "listen": True,
                "read_on_start": False,
                "periodic_interval_seconds": None,
            },
            publish_defaults_json={
                "enabled": True,
                "change_threshold": None,
            },
        )
    )

    with TestClient(app) as client:
        response = client.request(
            "DELETE",
            "/backoffice/source-model/delete?"
            "pks=tenant-backoffice;asset-backoffice;agent-backoffice;source-delete",
            headers={"referer": "http://testserver/backoffice/source-model/list"},
        )
        sources = client.get(
            "/tenants/tenant-backoffice/assets/asset-backoffice"
            "/agents/agent-backoffice/sources"
        ).json()

    assert response.status_code == 200
    assert not any(source["source_id"] == "source-delete" for source in sources)


@pytest.mark.asyncio
async def test_backoffice_can_delete_point_via_mounted_delete_route() -> None:
    app = create_app(settings=_settings(internal_mode=True))
    app.state.unit_of_work_factory = InMemoryUnitOfWorkFactory()
    await _seed_registry_tree(app)
    await CreatePoint(app.state.unit_of_work_factory()).execute(
        CreatePointCommand(
            tenant_code="tenant-backoffice",
            asset_code="asset-backoffice",
            agent_code="agent-backoffice",
            source_code="source-backoffice",
            point_code="point-delete",
            point_key="3%2F3%2F3",
            point_ref="3/3/3",
            name="Point Delete",
            value_type=ValueType.NUMBER,
            value_model="knx.dpt.9.001",
            signal_type=SignalType.SENSOR,
            enabled=True,
        )
    )

    with TestClient(app) as client:
        response = client.request(
            "DELETE",
            "/backoffice/point-model/delete?pks=tenant-backoffice;point-delete",
            headers={"referer": "http://testserver/backoffice/point-model/list"},
        )
        points = client.get(
            "/tenants/tenant-backoffice/assets/asset-backoffice"
            "/agents/agent-backoffice/sources/source-backoffice/points"
        ).json()

    assert response.status_code == 200
    assert not any(point["point_id"] == "point-delete" for point in points)


@pytest.mark.asyncio
async def test_backoffice_can_create_agent_runtime_config_revision_via_mounted_form() -> None:
    app = create_app(settings=_settings(internal_mode=True))
    app.state.unit_of_work_factory = InMemoryUnitOfWorkFactory()
    await _seed_registry_tree(app)

    with TestClient(app) as client:
        response = client.post(
            "/backoffice/agent-runtime-config-revision-model/create",
            data={
                AGENT_SELECTOR_FIELD: encode_agent_selection(
                    AgentSelection(
                        tenant_code="tenant-backoffice",
                        asset_code="asset-backoffice",
                        agent_code="agent-backoffice",
                    )
                ),
                "config_revision": "rev-ui",
                "issued_at": "2026-05-04T06:58:00Z",
                "agent_runtime_payload_json": '{"demo": true}',
                "save": "Save",
            },
            follow_redirects=False,
        )

    async with app.state.unit_of_work_factory() as unit_of_work:
        revision = await unit_of_work.agent_runtime_config_revisions.get(
            "tenant-backoffice",
            "asset-backoffice",
            "agent-backoffice",
            "rev-ui",
        )

    assert response.status_code == 302
    assert revision is not None
    assert revision.agent_runtime_payload_json == {"demo": True}


@pytest.mark.asyncio
async def test_backoffice_can_create_source_config_revision_via_mounted_form() -> None:
    app = create_app(settings=_settings(internal_mode=True))
    app.state.unit_of_work_factory = InMemoryUnitOfWorkFactory()
    await _seed_registry_tree(app)
    await CreateAgentRuntimeConfigRevision(app.state.unit_of_work_factory()).execute(
        CreateAgentRuntimeConfigRevisionCommand(
            tenant_code="tenant-backoffice",
            asset_code="asset-backoffice",
            agent_code="agent-backoffice",
            config_revision="rev-ui",
            issued_at=datetime(2026, 5, 4, 6, 58, tzinfo=UTC),
            agent_runtime_payload_json={"demo": True},
        )
    )

    with TestClient(app) as client:
        response = client.post(
            "/backoffice/source-config-revision-model/create",
            data={
                SOURCE_SELECTOR_FIELD: encode_source_selection(
                    SourceSelection(
                        tenant_code="tenant-backoffice",
                        asset_code="asset-backoffice",
                        agent_code="agent-backoffice",
                        source_code="source-backoffice",
                    )
                ),
                "source_config_revision": "src-rev-ui",
                "config_revision": "rev-ui",
                "issued_at": "2026-05-04T06:58:01Z",
                "source_payload_json": '{"demo": true}',
                "save": "Save",
            },
            follow_redirects=False,
        )

    async with app.state.unit_of_work_factory() as unit_of_work:
        revision = await unit_of_work.source_config_revisions.get(
            "tenant-backoffice",
            "asset-backoffice",
            "agent-backoffice",
            "source-backoffice",
            "src-rev-ui",
        )

    assert response.status_code == 302
    assert revision is not None
    assert revision.source_payload_json == {"demo": True}


@pytest.mark.asyncio
async def test_backoffice_config_revision_edit_and_delete_are_disabled() -> None:
    app = create_app(settings=_settings(internal_mode=True))
    app.state.unit_of_work_factory = InMemoryUnitOfWorkFactory()
    await _seed_registry_tree(app)
    await CreateAgentRuntimeConfigRevision(app.state.unit_of_work_factory()).execute(
        CreateAgentRuntimeConfigRevisionCommand(
            tenant_code="tenant-backoffice",
            asset_code="asset-backoffice",
            agent_code="agent-backoffice",
            config_revision="rev-disabled",
            issued_at=datetime(2026, 5, 4, 7, 0, tzinfo=UTC),
            agent_runtime_payload_json={"demo": True},
        )
    )

    with TestClient(app) as client:
        edit_response = client.get(
            "/backoffice/agent-runtime-config-revision-model/edit/"
            "tenant-backoffice;asset-backoffice;agent-backoffice;rev-disabled"
        )
        delete_response = client.request(
            "DELETE",
            "/backoffice/agent-runtime-config-revision-model/delete?"
            "pks=tenant-backoffice;asset-backoffice;agent-backoffice;rev-disabled",
        )

    assert edit_response.status_code == 403
    assert delete_response.status_code == 403


@pytest.mark.parametrize(("view", "model", "expected_columns"), LIST_VIEW_COLUMNS)
def test_backoffice_list_views_show_compact_column_sets(
    view: type[object],
    model: type[object],
    expected_columns: tuple[str, ...],
) -> None:
    assert [column.name for column in view.column_list] == list(expected_columns)
    assert [column.name for column in view.column_details_list] == [
        column.name for column in model.__table__.columns
    ]


@pytest.mark.asyncio
async def test_backoffice_agent_list_exposes_render_config_action() -> None:
    app = create_app(settings=_settings(internal_mode=True))
    app.state.unit_of_work_factory = InMemoryUnitOfWorkFactory()
    await _seed_registry_tree(app)

    agent_view = next(
        view for view in app.state.backoffice.views if isinstance(view, AgentBackofficeView)
    )

    with TestClient(app) as client:
        legacy_response = client.get("/backoffice/render-config")

    assert agent_view._custom_actions_in_list["render-agent-config"] == "Собрать config"
    assert agent_view._custom_actions_in_detail["render-agent-config"] == "Собрать config"
    assert legacy_response.status_code == 404


def test_sqladmin_dependency_stays_out_of_domain_and_application_layers() -> None:
    guarded_roots = [
        CONFIG_REGISTRY_SRC / "domain",
        CONFIG_REGISTRY_SRC / "application",
    ]
    for root in guarded_roots:
        for path in root.rglob("*.py"):
            assert "sqladmin" not in path.read_text(encoding="utf-8")


def test_custom_list_template_keeps_sqladmin_bulk_action_modals() -> None:
    template = (
        CONFIG_REGISTRY_SRC
        / "templates"
        / "sqladmin"
        / "list.html"
    ).read_text(encoding="utf-8")

    assert "sqladmin/modals/delete.html" in template
    assert "sqladmin/modals/list_action_confirmation.html" in template


@pytest.mark.asyncio
async def test_backoffice_agent_render_config_action_uses_application_use_cases() -> None:
    app = create_app(settings=_settings(internal_mode=True))
    app.state.unit_of_work_factory = InMemoryUnitOfWorkFactory()
    await _seed_registry_tree(app)

    with TestClient(app) as client:
        response = client.get(
            "/backoffice/agent-model/action/render-agent-config",
            params={"pks": "tenant-backoffice;asset-backoffice;agent-backoffice"},
            headers={"referer": "http://testserver/backoffice/agent-model/list"},
        )

    html = response.text
    assert response.status_code == 200
    assert "Собрать config" in html
    assert "Успешно обработано агентов: 1." in html
    assert "agent-backoffice" in html
    assert "revision=backoffice-" in html
    assert "outbox_records=2" in html
    assert "Вернуться в список" in html


@pytest.mark.asyncio
async def test_backoffice_agent_render_config_action_backfills_legacy_settings() -> None:
    app = create_app(settings=_settings(internal_mode=True))
    app.state.unit_of_work_factory = InMemoryUnitOfWorkFactory()
    await _seed_registry_tree(
        app,
        acquisition_defaults={},
        publish_defaults={},
        point_acquisition={},
        point_publish={},
    )

    with TestClient(app) as client:
        response = client.get(
            "/backoffice/agent-model/action/render-agent-config",
            params={"pks": "tenant-backoffice;asset-backoffice;agent-backoffice"},
            headers={"referer": "http://testserver/backoffice/agent-model/list"},
        )

    html = response.text
    assert response.status_code == 200
    assert "Успешно обработано агентов: 1." in html
    assert "Создано записей в config_outbox: 2." in html
    assert "payload violates contract" not in html


@pytest.mark.asyncio
async def test_backoffice_outbox_actions_use_application_use_cases() -> None:
    app = create_app()
    await _render_backoffice_config(app)
    async with app.state.unit_of_work_factory() as unit_of_work:
        records = await unit_of_work.config_outbox.reserve_available(
            limit=1,
            now=datetime.now(UTC),
            lease_duration=timedelta(seconds=30),
        )
        await unit_of_work.commit()
    outbox_id = records[0].outbox_id

    retry_response = await ConfigOutboxActionsBackofficeView().retry_outbox_record(
        FakeJsonRequest(
            app,
            {
                "outbox_id": str(outbox_id),
                "reason": "Manual retry from test",
                "next_attempt_at": "2026-05-03T12:00:01Z",
            },
        )
    )
    dead_letter_response = await (
        ConfigOutboxActionsBackofficeView().dead_letter_outbox_record(
            FakeJsonRequest(
                app,
                {
                    "outbox_id": str(outbox_id),
                    "reason": "Manual dead-letter from test",
                },
            )
        )
    )

    retry_body = json.loads(retry_response.body)
    dead_letter_body = json.loads(dead_letter_response.body)
    assert retry_response.status_code == 200
    assert retry_body["status"] == "retry"
    assert retry_body["last_error"] == "Manual retry from test"
    assert dead_letter_response.status_code == 200
    assert dead_letter_body["status"] == "dead_letter"
    assert dead_letter_body["last_error"] == "Manual dead-letter from test"


def _settings(*, internal_mode: bool) -> ConfigRegistrySettings:
    return ConfigRegistrySettings(
        internal_mode=internal_mode,
        database_url="postgresql+asyncpg://idp:password@127.0.0.1:1/idp_config_registry",
    )


def _has_route_prefix(app: object, prefix: str) -> bool:
    routes = getattr(app, "routes")
    return any(str(getattr(route, "path", "")).startswith(prefix) for route in routes)


class FakeJsonRequest:
    def __init__(self, app: object, payload: dict[str, Any]) -> None:
        self.app = app
        self._payload = payload

    async def json(self) -> dict[str, Any]:
        return self._payload


class FakePageRequest:
    def __init__(self, app: object) -> None:
        self.app = app


async def _seed_registry_tree(
    app: object,
    *,
    acquisition_defaults: dict[str, object] | None = None,
    publish_defaults: dict[str, object] | None = None,
    point_acquisition: dict[str, object] | None = None,
    point_publish: dict[str, object] | None = None,
) -> None:
    unit_of_work_factory = app.state.unit_of_work_factory
    await CreateTenant(unit_of_work_factory()).execute(
        CreateTenantCommand(
            tenant_code="tenant-backoffice",
            name="Tenant Backoffice",
        )
    )
    await CreateAsset(unit_of_work_factory()).execute(
        CreateAssetCommand(
            tenant_code="tenant-backoffice",
            asset_code="asset-backoffice",
            name="Asset Backoffice",
        )
    )
    await CreateAgent(unit_of_work_factory()).execute(
        CreateAgentCommand(
            tenant_code="tenant-backoffice",
            asset_code="asset-backoffice",
            agent_code="agent-backoffice",
        )
    )
    await CreateSource(unit_of_work_factory()).execute(
        CreateSourceCommand(
            tenant_code="tenant-backoffice",
            asset_code="asset-backoffice",
            agent_code="agent-backoffice",
            source_code="source-backoffice",
            source_type="knx",
            acquisition_defaults_json=(
                dict(acquisition_defaults)
                if acquisition_defaults is not None
                else {
                    "listen": True,
                    "read_on_start": False,
                    "periodic_interval_seconds": None,
                }
            ),
            publish_defaults_json=(
                dict(publish_defaults)
                if publish_defaults is not None
                else {
                    "enabled": True,
                    "change_threshold": None,
                }
            ),
        )
    )
    await CreatePoint(unit_of_work_factory()).execute(
        CreatePointCommand(
            tenant_code="tenant-backoffice",
            asset_code="asset-backoffice",
            agent_code="agent-backoffice",
            source_code="source-backoffice",
            point_code="point-backoffice",
            point_key="1%2F2%2F3",
            point_ref="1/2/3",
            name="Point Backoffice",
            value_type=ValueType.NUMBER,
            value_model="knx.dpt.9.001",
            signal_type=SignalType.SENSOR,
            enabled=True,
            acquisition_json=(
                dict(point_acquisition)
                if point_acquisition is not None
                else {}
            ),
            publish_json=(
                dict(point_publish)
                if point_publish is not None
                else {}
            ),
        )
    )


async def _render_backoffice_config(app: object) -> None:
    await _seed_registry_tree(app)
    await render_agent_config_for_agent(
        FakePageRequest(app),
        tenant_code="tenant-backoffice",
        asset_code="asset-backoffice",
        agent_code="agent-backoffice",
        issued_at=datetime(2026, 5, 3, 12, 0, tzinfo=UTC),
    )
