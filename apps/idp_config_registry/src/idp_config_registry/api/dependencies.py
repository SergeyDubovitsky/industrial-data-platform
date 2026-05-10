from __future__ import annotations

from collections.abc import Callable

from fastapi import Request

from idp_config_registry.application.ports.config_validation import (
    ConfigPayloadValidator,
)
from idp_config_registry.application.ports.unit_of_work import UnitOfWork

UnitOfWorkFactory = Callable[[], UnitOfWork]


def get_unit_of_work_factory(request: Request) -> UnitOfWorkFactory:
    return request.app.state.unit_of_work_factory


def get_config_payload_validator(request: Request) -> ConfigPayloadValidator:
    return request.app.state.config_payload_validator
