from __future__ import annotations

from importlib.resources import files

from fastapi import FastAPI
from sqladmin import Admin, BaseView, ModelView
from sqlalchemy.ext.asyncio import AsyncEngine

from idp_config_registry.infrastructure.backoffice_actions import (
    ConfigOutboxActionsBackofficeView,
)
from idp_config_registry.infrastructure.backoffice_business_views import (
    AgentBackofficeView,
    AssetBackofficeView,
    PointBackofficeView,
    SourceBackofficeView,
    TenantBackofficeView,
)
from idp_config_registry.infrastructure.backoffice_config_views import (
    AgentRuntimeConfigRevisionBackofficeView,
    ConfigOutboxBackofficeView,
    SourceConfigRevisionBackofficeView,
)
from idp_config_registry.infrastructure.backoffice_support import (
    BackofficeStateContextMiddleware,
)

BACKOFFICE_VIEWS: tuple[type[ModelView], ...] = (
    TenantBackofficeView,
    AssetBackofficeView,
    AgentBackofficeView,
    SourceBackofficeView,
    PointBackofficeView,
    AgentRuntimeConfigRevisionBackofficeView,
    SourceConfigRevisionBackofficeView,
    ConfigOutboxBackofficeView,
)

BACKOFFICE_CUSTOM_VIEWS: tuple[type[BaseView], ...] = (
    ConfigOutboxActionsBackofficeView,
)


def mount_backoffice(app: FastAPI, *, engine: AsyncEngine) -> Admin:
    admin = Admin(
        app=app,
        engine=engine,
        base_url="/backoffice",
        title="Config Registry Backoffice",
        templates_dir=str(files("idp_config_registry").joinpath("templates")),
    )
    admin.admin.state.root_app = app
    admin.admin.add_middleware(BackofficeStateContextMiddleware)
    for view in BACKOFFICE_VIEWS:
        admin.add_view(view)
    for view in BACKOFFICE_CUSTOM_VIEWS:
        admin.add_view(view)
    return admin


__all__ = [
    "AgentBackofficeView",
    "AssetBackofficeView",
    "BACKOFFICE_CUSTOM_VIEWS",
    "BACKOFFICE_VIEWS",
    "ConfigOutboxActionsBackofficeView",
    "ConfigOutboxBackofficeView",
    "PointBackofficeView",
    "AgentRuntimeConfigRevisionBackofficeView",
    "SourceBackofficeView",
    "SourceConfigRevisionBackofficeView",
    "TenantBackofficeView",
    "mount_backoffice",
]
