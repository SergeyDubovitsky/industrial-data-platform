from __future__ import annotations

import re
from enum import StrEnum


class DomainValidationError(ValueError):
    """Raised when a platform configuration domain value violates contracts."""


class TenantStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class AssetStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class AgentStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"
    RETIRED = "retired"


class ValueType(StrEnum):
    BOOLEAN = "boolean"
    NUMBER = "number"
    STRING = "string"


class SignalType(StrEnum):
    COMMAND = "command"
    FEEDBACK = "feedback"
    STATUS = "status"
    SENSOR = "sensor"


class ConfigRevisionStatus(StrEnum):
    DRAFT = "draft"
    RENDERED = "rendered"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    FAILED = "failed"


class ConfigOutboxStatus(StrEnum):
    PENDING = "pending"
    INFLIGHT = "inflight"
    PUBLISHED = "published"
    RETRY = "retry"
    DEAD_LETTER = "dead_letter"


_PATH_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,127}$")
_POINT_KEY_PATTERN = re.compile(r"^(?:[A-Za-z0-9._~-]|%[0-9A-F]{2})+$")


def require_non_empty(value: str, *, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise DomainValidationError(f"{field_name} must be non-empty")
    return normalized


def require_path_id(value: str, *, field_name: str) -> str:
    normalized = require_non_empty(value, field_name=field_name)
    if _PATH_ID_PATTERN.fullmatch(normalized) is None:
        raise DomainValidationError(
            f"{field_name} must match MQTT path-id pattern"
        )
    return normalized


def require_point_key(value: str) -> str:
    normalized = require_non_empty(value, field_name="point_key")
    if _POINT_KEY_PATTERN.fullmatch(normalized) is None:
        raise DomainValidationError("point_key must match edge contract pattern")
    return normalized
