from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from idp_config_registry.application.errors import ConfigPayloadValidationError


class JsonSchemaConfigPayloadValidator:
    def __init__(
        self,
        *,
        runtime_schema: dict[str, Any],
        source_schema: dict[str, Any],
        config_delivery_schema: dict[str, Any],
    ) -> None:
        Draft202012Validator.check_schema(runtime_schema)
        Draft202012Validator.check_schema(source_schema)
        Draft202012Validator.check_schema(config_delivery_schema)
        format_checker = FormatChecker()
        self._runtime_validator = Draft202012Validator(
            runtime_schema,
            format_checker=format_checker,
        )
        self._source_validator = Draft202012Validator(
            source_schema,
            format_checker=format_checker,
        )
        self._config_delivery_validator = Draft202012Validator(
            config_delivery_schema,
            format_checker=format_checker,
        )

    @classmethod
    def from_contract_dirs(
        cls,
        *,
        edge_contract_dir: Path,
        kafka_contract_dir: Path,
    ) -> JsonSchemaConfigPayloadValidator:
        return cls(
            runtime_schema=_load_schema(
                edge_contract_dir / "idp.edge.agent-runtime-config.v1.schema.json"
            ),
            source_schema=_load_schema(
                edge_contract_dir / "idp.edge.source-config.v1.schema.json"
            ),
            config_delivery_schema=_load_schema(
                kafka_contract_dir / "idp.edge.config.delivery.v1.schema.json"
            ),
        )

    @classmethod
    def from_contract_dir(cls, contract_dir: Path) -> JsonSchemaConfigPayloadValidator:
        return cls.from_contract_dirs(
            edge_contract_dir=contract_dir,
            kafka_contract_dir=contract_dir.parents[1] / "kafka" / "schemas",
        )

    def validate_agent_runtime_config(self, payload: dict[str, Any]) -> None:
        _raise_if_invalid(
            message_type="idp.edge.agent-runtime-config.v1",
            validator=self._runtime_validator,
            payload=payload,
        )

    def validate_source_config(self, payload: dict[str, Any]) -> None:
        _raise_if_invalid(
            message_type="idp.edge.source-config.v1",
            validator=self._source_validator,
            payload=payload,
        )

    def validate_config_delivery(self, payload: dict[str, Any]) -> None:
        _raise_if_invalid(
            message_type="idp.edge.config.delivery.v1",
            validator=self._config_delivery_validator,
            payload=payload,
        )


def _load_schema(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    if not isinstance(raw, dict):
        raise ValueError(f"JSON Schema {path} must be an object")
    return raw


def _raise_if_invalid(
    *,
    message_type: str,
    validator: Draft202012Validator,
    payload: dict[str, Any],
) -> None:
    errors = sorted(validator.iter_errors(payload), key=lambda error: error.json_path)
    if errors:
        raise ConfigPayloadValidationError(
            message_type,
            [f"{error.json_path}: {error.message}" for error in errors],
        )
