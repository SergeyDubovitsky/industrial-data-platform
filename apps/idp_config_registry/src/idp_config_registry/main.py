from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from idp_config_registry.api.routers import (
    agents,
    assets,
    health,
    points,
    sources,
    tenants,
)
from idp_config_registry.application.ports.unit_of_work import UnitOfWork
from idp_config_registry.infrastructure.backoffice import mount_backoffice
from idp_config_registry.infrastructure.json_schema_validator import (
    JsonSchemaConfigPayloadValidator,
)
from idp_config_registry.infrastructure.memory.unit_of_work import (
    InMemoryUnitOfWorkFactory,
)
from idp_config_registry.infrastructure.postgres.unit_of_work import (
    PostgresUnitOfWorkFactory,
)
from idp_config_registry.settings import ConfigRegistrySettings


def create_app(
    settings: ConfigRegistrySettings | None = None,
    unit_of_work_factory: Callable[[], UnitOfWork] | None = None,
) -> FastAPI:
    resolved_settings = settings or ConfigRegistrySettings.from_env()
    resolved_unit_of_work_factory = unit_of_work_factory
    if resolved_unit_of_work_factory is None and resolved_settings.database_url:
        resolved_unit_of_work_factory = PostgresUnitOfWorkFactory.from_url(
            resolved_settings.database_url
        )
    if resolved_unit_of_work_factory is None:
        resolved_unit_of_work_factory = InMemoryUnitOfWorkFactory()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            dispose = getattr(app.state.unit_of_work_factory, "dispose", None)
            if dispose is not None:
                await dispose()

    app = FastAPI(
        title="Industrial Data Platform Config Registry",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )
    app.state.unit_of_work_factory = resolved_unit_of_work_factory
    app.state.config_payload_validator = (
        JsonSchemaConfigPayloadValidator.from_contract_dir(
            Path.cwd() / "docs" / "contracts" / "edge-telemetry-agent" / "schemas"
        )
    )
    app.include_router(health.router)
    app.include_router(tenants.router)
    app.include_router(assets.router)
    app.include_router(agents.router)
    app.include_router(sources.router)
    app.include_router(points.router)
    app.state.backoffice_enabled = False
    if resolved_settings.internal_mode and isinstance(
        resolved_unit_of_work_factory,
        PostgresUnitOfWorkFactory,
    ):
        app.state.backoffice = mount_backoffice(
            app,
            engine=resolved_unit_of_work_factory.session_manager.engine,
        )
        app.state.backoffice_enabled = True
    return app
