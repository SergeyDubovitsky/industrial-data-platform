from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from idp_synthetic_config.models import SyntheticModel, ValueProfile

JsonObject = dict[str, Any]


@dataclass(frozen=True)
class EmulatorPoint:
    source_id: str
    point_ref: str
    point_key: str
    name: str
    description: str | None
    value_type: str
    value_model: str
    signal_type: str
    unit: str | None
    tags: dict[str, str]
    periodic_interval_seconds: float
    change_threshold: float | None
    read_on_start: bool
    profile: ValueProfile

    @property
    def writable(self) -> bool:
        return self.signal_type == "command"

    def to_dict(self) -> JsonObject:
        return {
            "source_id": self.source_id,
            "point_ref": self.point_ref,
            "point_key": self.point_key,
            "name": self.name,
            "description": self.description,
            "value_type": self.value_type,
            "value_model": self.value_model,
            "signal_type": self.signal_type,
            "unit": self.unit,
            "tags": dict(self.tags),
            "periodic_interval_seconds": self.periodic_interval_seconds,
            "change_threshold": self.change_threshold,
            "read_on_start": self.read_on_start,
            "writable": self.writable,
            "value_profile": self.profile.to_dict(),
        }


@dataclass(frozen=True)
class EmulatorPlan:
    host: str
    port: int
    source_id: str
    devices: int
    points: tuple[EmulatorPoint, ...]
    emission_interval_seconds: float | None = None
    enable_writes: bool = True

    @property
    def point_count(self) -> int:
        return len(self.points)

    @property
    def stream_points(self) -> tuple[EmulatorPoint, ...]:
        return tuple(point for point in self.points if point.signal_type != "command")

    @property
    def command_points(self) -> tuple[EmulatorPoint, ...]:
        return tuple(point for point in self.points if point.signal_type == "command")

    def point_by_ref_or_key(
        self,
        *,
        point_ref: str | None,
        point_key: str | None,
    ) -> EmulatorPoint | None:
        for point in self.points:
            if point_ref is not None and point.point_ref == point_ref:
                return point
            if point_key is not None and point.point_key == point_key:
                return point
        return None

    def to_dict(self) -> JsonObject:
        return {
            "host": self.host,
            "port": self.port,
            "source_id": self.source_id,
            "enable_writes": self.enable_writes,
            "stats": {
                "devices": self.devices,
                "points": self.point_count,
                "stream_points": len(self.stream_points),
                "command_points": len(self.command_points),
            },
            "points": [point.to_dict() for point in self.points],
        }


def build_emulator_plan(
    model: SyntheticModel,
    *,
    host: str,
    port: int,
    source_id: str | None = None,
    interval_seconds: float | None = None,
    enable_writes: bool = True,
) -> EmulatorPlan:
    if not model.sources:
        raise ValueError("synthetic model must contain at least one source")

    selected_source_id = source_id or model.sources[0].source_id
    source = next(
        (item for item in model.sources if item.source_id == selected_source_id),
        None,
    )
    if source is None:
        raise ValueError(f"source_id {selected_source_id!r} not found in synthetic model")

    source_config = source.source_config_payload(
        tenant_id=model.tenant.tenant_id,
        asset_id=model.asset.asset_id,
        agent_id=model.agent.agent_id,
        config_revision="local-plan",
        source_config_revision=f"local-plan-{source.source_id}",
    )

    return build_emulator_plan_from_source_config(
        source_config,
        value_profiles=model.value_profiles,
        devices=len(model.devices),
        host=host,
        port=port,
        emission_interval_seconds=interval_seconds,
        enable_writes=enable_writes,
    )


def build_emulator_plan_from_source_config(
    source_config: Mapping[str, object],
    *,
    value_profiles: Iterable[ValueProfile],
    devices: int = 0,
    host: str | None = None,
    port: int | None = None,
    emission_interval_seconds: float | None = None,
    enable_writes: bool = True,
) -> EmulatorPlan:
    message_type = source_config.get("message_type")
    if message_type is not None and message_type != "idp.edge.source-config.v1":
        raise ValueError("source_config message_type must be idp.edge.source-config.v1")

    tenant_id = _required_string(source_config, "tenant_id")
    asset_id = _required_string(source_config, "asset_id")
    source_id = _required_string(source_config, "source_id")
    connection = _required_mapping(source_config, "connection")
    acquisition_defaults = _optional_mapping(source_config, "acquisition_defaults")
    points_payload = _required_list(source_config, "points")

    resolved_host, resolved_port = _endpoint(
        connection,
        host_override=host,
        port_override=port,
    )
    profiles_by_point_id = {profile.point_id: profile for profile in value_profiles}
    points: list[EmulatorPoint] = []
    for item in points_payload:
        if not isinstance(item, Mapping):
            raise ValueError("source_config points must contain objects")
        point_key = _required_string(item, "point_key")
        point_ref = _required_string(item, "point_ref")
        point_id = f"{tenant_id}|{asset_id}|{source_id}|{point_key}"
        profile = profiles_by_point_id.get(point_id)
        if profile is None:
            raise ValueError(f"value profile missing for point_id {point_id!r}")

        acquisition = _optional_mapping(item, "acquisition")
        publish = _optional_mapping(item, "publish")
        periodic = acquisition.get(
            "periodic_interval_seconds",
            acquisition_defaults.get("periodic_interval_seconds"),
        )
        points.append(
            EmulatorPoint(
                source_id=source_id,
                point_ref=point_ref,
                point_key=point_key,
                name=_required_string(item, "name"),
                description=_optional_string(item, "description"),
                value_type=_required_string(item, "value_type"),
                value_model=_required_string(item, "value_model"),
                signal_type=_required_string(item, "signal_type"),
                unit=_optional_string(item, "unit"),
                tags=_string_mapping(_optional_mapping(item, "tags")),
                periodic_interval_seconds=_positive_float(periodic, default=60.0),
                change_threshold=_optional_float(publish.get("change_threshold")),
                read_on_start=bool(acquisition.get("read_on_start", False)),
                profile=profile,
            )
        )

    return EmulatorPlan(
        host=resolved_host,
        port=resolved_port,
        source_id=source_id,
        devices=devices,
        points=tuple(points),
        emission_interval_seconds=emission_interval_seconds,
        enable_writes=enable_writes,
    )


def _endpoint(
    connection: Mapping[str, object],
    *,
    host_override: str | None,
    port_override: int | None,
) -> tuple[str, int]:
    host = host_override or _first(connection, "host", "tcp_host", "gateway_ip")
    port = port_override if port_override is not None else _first(
        connection,
        "port",
        "tcp_port",
        "gateway_port",
    )
    if not isinstance(host, str) or not host:
        raise ValueError("source connection host is missing")
    if isinstance(port, bool) or not isinstance(port, int):
        raise ValueError("source connection port is missing")
    return host, port


def _first(mapping: Mapping[str, object], *keys: str) -> object:
    for key in keys:
        value = mapping.get(key)
        if value is not None:
            return value
    return None


def _required_string(mapping: Mapping[str, object], field_name: str) -> str:
    value = mapping.get(field_name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _optional_string(mapping: Mapping[str, object], field_name: str) -> str | None:
    value = mapping.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string or null")
    return value


def _required_mapping(
    mapping: Mapping[str, object],
    field_name: str,
) -> Mapping[str, object]:
    value = mapping.get(field_name)
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be an object")
    return value


def _optional_mapping(
    mapping: Mapping[str, object],
    field_name: str,
) -> Mapping[str, object]:
    value = mapping.get(field_name)
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be an object")
    return value


def _required_list(mapping: Mapping[str, object], field_name: str) -> list[object]:
    value = mapping.get(field_name)
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be an array")
    return value


def _string_mapping(mapping: Mapping[str, object]) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in mapping.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValueError("tags must be a string-to-string object")
        result[key] = value
    return result


def _positive_float(value: object, *, default: float) -> float:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError("periodic_interval_seconds must be a number")
    resolved = float(value)
    if resolved <= 0:
        raise ValueError("periodic_interval_seconds must be positive")
    return resolved


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError("change_threshold must be a number or null")
    return float(value)
