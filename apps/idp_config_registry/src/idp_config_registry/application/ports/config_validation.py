from __future__ import annotations

from typing import Any, Protocol


class ConfigPayloadValidator(Protocol):
    def validate_agent_runtime_config(self, payload: dict[str, Any]) -> None: ...

    def validate_source_config(self, payload: dict[str, Any]) -> None: ...

    def validate_config_delivery(self, payload: dict[str, Any]) -> None: ...
