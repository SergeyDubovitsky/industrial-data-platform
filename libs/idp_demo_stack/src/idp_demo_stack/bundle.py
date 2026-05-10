from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from idp_demo_stack.models import BundlePoint, BundleSource, ConfigBundle

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover
    yaml = None


ENV_PLACEHOLDER_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def load_bundle(path: Path) -> ConfigBundle:
    raw = _load_document(path)
    if not isinstance(raw, dict):
        raise ValueError(f"Bundle {path} must be a mapping")
    sources_raw = raw.get("sources")
    if not isinstance(sources_raw, list) or not sources_raw:
        raise ValueError(f"Bundle {path} must contain a non-empty sources list")

    sources: list[BundleSource] = []
    for source_raw in sources_raw:
        if not isinstance(source_raw, dict):
            raise ValueError("Every source entry must be a mapping")
        points_raw = source_raw.get("points")
        if not isinstance(points_raw, list):
            raise ValueError("Every source entry must contain a points list")
        points = tuple(_to_point(item) for item in points_raw)
        sources.append(
            BundleSource(
                source_id=_required_string(source_raw, "source_id"),
                source_config_revision=_required_string(source_raw, "source_config_revision"),
                source_type=_required_string(source_raw, "source_type"),
                enabled=_required_bool(source_raw, "enabled"),
                connection=_required_mapping(source_raw, "connection"),
                acquisition_defaults=_required_mapping(source_raw, "acquisition_defaults"),
                publish_defaults=_required_mapping(source_raw, "publish_defaults"),
                points=points,
            )
        )
    return ConfigBundle(
        tenant_id=_required_string(raw, "tenant_id"),
        asset_id=_required_string(raw, "asset_id"),
        agent_id=_required_string(raw, "agent_id"),
        config_revision=_required_string(raw, "config_revision"),
        issued_at=_required_string(raw, "issued_at"),
        sources=tuple(sources),
    )


def _to_point(raw: object) -> BundlePoint:
    if not isinstance(raw, dict):
        raise ValueError("Point entry must be a mapping")
    return BundlePoint(
        point_key=_required_string(raw, "point_key"),
        point_ref=_required_string(raw, "point_ref"),
        name=_required_string(raw, "name"),
        description=_optional_string(raw.get("description")),
        signal_type=_required_string(raw, "signal_type"),
        value_type=_required_string(raw, "value_type"),
        value_model=_required_string(raw, "value_model"),
        unit=_optional_string(raw.get("unit")),
        acquisition=_required_mapping(raw, "acquisition"),
        publish=_required_mapping(raw, "publish"),
        tags=_string_mapping(raw.get("tags", {})),
    )


def _load_document(path: Path) -> object:
    if path.suffix.lower() == ".json":
        with path.open("r", encoding="utf-8") as handle:
            return _expand_env_placeholders(json.load(handle), source=path)
    if yaml is None:
        raise RuntimeError("PyYAML is required to load YAML demo bundles")
    with path.open("r", encoding="utf-8") as handle:
        return _expand_env_placeholders(yaml.safe_load(handle), source=path)


def _expand_env_placeholders(value: object, *, source: Path) -> object:
    if isinstance(value, str):
        return ENV_PLACEHOLDER_PATTERN.sub(
            lambda match: _required_env_value(match.group(1), source=source),
            value,
        )
    if isinstance(value, list):
        return [_expand_env_placeholders(item, source=source) for item in value]
    if isinstance(value, dict):
        return {
            key: _expand_env_placeholders(item, source=source)
            for key, item in value.items()
        }
    return value


def _required_env_value(env_name: str, *, source: Path) -> str:
    value = os.getenv(env_name)
    if value is None:
        raise ValueError(f"Environment variable {env_name!r} referenced in {source} is not set")
    return value


def _required_string(raw: dict[str, object], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return value.strip()


def _required_bool(raw: dict[str, object], key: str) -> bool:
    value = raw.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"{key} must be a boolean")
    return value


def _required_mapping(raw: dict[str, object], key: str) -> dict[str, Any]:
    value = raw.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be a mapping")
    return dict(value)


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Optional text fields must be strings or null")
    stripped = value.strip()
    return stripped or None


def _string_mapping(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError("tags must be a mapping")
    result: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, str):
            raise ValueError("tags must contain only string keys and values")
        result[key] = item
    return result
