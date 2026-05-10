from __future__ import annotations

from typing import Any


def default_acquisition_settings() -> dict[str, Any]:
    return {
        "listen": True,
        "read_on_start": False,
        "periodic_interval_seconds": None,
    }


def default_publish_settings() -> dict[str, Any]:
    return {
        "enabled": True,
        "change_threshold": None,
    }


def normalize_acquisition_settings(
    value: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        **default_acquisition_settings(),
        **(value or {}),
    }


def normalize_publish_settings(
    value: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        **default_publish_settings(),
        **(value or {}),
    }
