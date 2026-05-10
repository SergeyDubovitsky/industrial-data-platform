from __future__ import annotations

import json
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

from sqladmin import ModelView
from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from idp_config_registry.application.config_defaults import (
    default_acquisition_settings as _default_acquisition_settings,
)
from idp_config_registry.application.config_defaults import (
    default_publish_settings as _default_publish_settings,
)

_CURRENT_BACKOFFICE_STATE: ContextVar[Any | None] = ContextVar(
    "current_backoffice_state",
    default=None,
)


class BackofficeStateContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        state = scope["app"].state
        root_app = getattr(state, "root_app", None)
        resolved_state = root_app.state if root_app is not None else state
        token = _CURRENT_BACKOFFICE_STATE.set(resolved_state)
        try:
            await self.app(scope, receive, send)
        finally:
            _CURRENT_BACKOFFICE_STATE.reset(token)


class BackofficeModelView(ModelView):
    can_view_details = True
    can_export = True
    form_include_pk = True
    page_size = 50
    page_size_options = [25, 50, 100]

    @property
    def show_bulk_actions(self) -> bool:
        return self.can_delete or bool(self._custom_actions_in_list)


class BusinessBackofficeModelView(BackofficeModelView):
    can_create = True
    can_edit = True
    can_delete = True


class AppendOnlyBackofficeModelView(BackofficeModelView):
    can_create = True
    can_edit = False
    can_delete = False


class ReadOnlyBackofficeModelView(BackofficeModelView):
    can_create = False
    can_edit = False
    can_delete = False


def all_model_columns(model: type[Any]) -> list[Any]:
    return list(model.__table__.columns)


def model_columns(model: type[Any], *names: str) -> list[Any]:
    return [getattr(model, name) for name in names]


def get_request_state(request: Request) -> Any:
    state = request.app.state
    if hasattr(state, "unit_of_work_factory"):
        return state
    root_app = getattr(state, "root_app", None)
    if root_app is not None and hasattr(root_app.state, "unit_of_work_factory"):
        return root_app.state
    raise AttributeError("Backoffice request state is missing unit_of_work_factory")


def get_current_state() -> Any:
    state = _CURRENT_BACKOFFICE_STATE.get()
    if state is None or not hasattr(state, "unit_of_work_factory"):
        raise RuntimeError("Backoffice state is unavailable outside request scope")
    return state


def optional_string(value: object) -> str | None:
    if value is None or value == "":
        return None
    return str(value)


def json_object(value: object, *, field_name: str) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            raise ValueError(f"{field_name} must be a JSON object")
        parsed = json.loads(normalized)
        if isinstance(parsed, dict):
            return parsed
    raise ValueError(f"{field_name} must be a JSON object")


def optional_bool(value: object, *, default: bool) -> bool:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"false", "0", "off", "no"}:
            return False
        if normalized in {"true", "1", "on", "yes"}:
            return True
    return bool(value)


def parse_issued_at(value: object) -> datetime:
    if value is None or value == "":
        return datetime.now(UTC)
    if not isinstance(value, str):
        raise ValueError("issued_at must be an ISO-8601 string")
    normalized = value.removesuffix("Z") + "+00:00" if value.endswith("Z") else value
    return datetime.fromisoformat(normalized)


def format_datetime(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def default_acquisition_settings() -> dict[str, object]:
    return _default_acquisition_settings()


def default_publish_settings() -> dict[str, object]:
    return _default_publish_settings()
