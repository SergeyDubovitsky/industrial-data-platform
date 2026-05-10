from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class EndpointProfile:
    gateway_ip: str
    gateway_port: int
    route_back: bool


DEFAULT_PROFILE_NAMES = ("external", "local")


def default_profiles() -> dict[str, EndpointProfile]:
    return {
        "external": EndpointProfile(
            gateway_ip=os.getenv("KNX_EXTERNAL_GATEWAY_IP", "203.0.113.234"),
            gateway_port=_env_int("KNX_EXTERNAL_GATEWAY_PORT", 7171),
            route_back=_env_bool("KNX_EXTERNAL_ROUTE_BACK", True),
        ),
        "local": EndpointProfile(
            gateway_ip=os.getenv("KNX_LOCAL_GATEWAY_IP", "192.0.2.177"),
            gateway_port=_env_int("KNX_LOCAL_GATEWAY_PORT", 3671),
            route_back=_env_bool("KNX_LOCAL_ROUTE_BACK", False),
        ),
    }


def resolve_endpoint_profile(
    profile_name: str,
    gateway_ip: str | None = None,
    gateway_port: int | None = None,
    route_back: bool | None = None,
    profiles: Mapping[str, EndpointProfile] | None = None,
) -> EndpointProfile:
    profile_map = default_profiles() if profiles is None else profiles
    profile = profile_map[profile_name]
    return EndpointProfile(
        gateway_ip=gateway_ip or profile.gateway_ip,
        gateway_port=gateway_port or profile.gateway_port,
        route_back=profile.route_back if route_back is None else route_back,
    )


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    return int(raw)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Unsupported boolean value for {name}: {raw}")
