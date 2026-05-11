from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Mapping
from datetime import datetime
from typing import Any

from edge_telemetry_agent.domain.config import SourceDefinition
from edge_telemetry_agent.domain.events import Observation, ScalarValue


class SyntheticKnxProtocolError(RuntimeError):
    """Raised when the local synthetic KNX stream sends an invalid event."""


class SyntheticKnxObservationClient:
    def __init__(
        self,
        *,
        source_id: str,
        host: str,
        port: int,
        connect_timeout_seconds: float = 10.0,
    ) -> None:
        self._source_id = source_id
        self._host = host
        self._port = port
        self._connect_timeout_seconds = connect_timeout_seconds

    @classmethod
    def from_source(cls, source: SourceDefinition) -> SyntheticKnxObservationClient:
        host = _string_connection_value(
            source.connection,
            "gateway_ip",
            default="127.0.0.1",
        )
        port = _int_connection_value(source.connection, "gateway_port", default=3671)
        return cls(source_id=source.source_id, host=host, port=port)

    async def observations(self) -> AsyncIterator[Observation]:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(self._host, self._port),
            timeout=self._connect_timeout_seconds,
        )
        try:
            while True:
                line = await reader.readline()
                if not line:
                    return
                yield _observation_from_line(line, expected_source_id=self._source_id)
        finally:
            writer.close()
            await writer.wait_closed()


def _observation_from_line(line: bytes, *, expected_source_id: str) -> Observation:
    try:
        payload = json.loads(line.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SyntheticKnxProtocolError("synthetic KNX event must be JSON line") from exc
    if not isinstance(payload, dict):
        raise SyntheticKnxProtocolError("synthetic KNX event must be a JSON object")
    source_id = _required_string(payload, "source_id")
    if source_id != expected_source_id:
        raise SyntheticKnxProtocolError(
            f"synthetic KNX event source_id={source_id!r} does not match "
            f"configured source_id={expected_source_id!r}"
        )
    return Observation(
        source_id=source_id,
        point_ref=_required_string(payload, "point_ref"),
        observation_mode=_required_observation_mode(payload),
        value=_optional_scalar(payload.get("value")),
        value_raw=_optional_string(payload.get("value_raw")),
        quality=_required_quality(payload),
        observed_at=_parse_ts(payload.get("ts")),
    )


def _required_observation_mode(payload: Mapping[str, Any]) -> str:
    value = _required_string(payload, "observation_mode")
    if value not in {"listen", "read_on_start", "periodic_read"}:
        raise SyntheticKnxProtocolError(f"unsupported observation_mode={value!r}")
    return value


def _required_quality(payload: Mapping[str, Any]) -> str:
    value = str(payload.get("quality", "good"))
    if value not in {"good", "uncertain", "bad"}:
        raise SyntheticKnxProtocolError(f"unsupported quality={value!r}")
    return value


def _parse_ts(value: object) -> datetime:
    if not isinstance(value, str) or not value:
        raise SyntheticKnxProtocolError("synthetic KNX event ts must be a string")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SyntheticKnxProtocolError(f"invalid synthetic KNX event ts={value!r}") from exc


def _optional_scalar(value: object) -> ScalarValue | None:
    if value is None or isinstance(value, bool | int | float | str):
        return value
    raise SyntheticKnxProtocolError("synthetic KNX event value must be scalar or null")


def _required_string(payload: Mapping[str, Any], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value:
        raise SyntheticKnxProtocolError(
            f"synthetic KNX event {field_name} must be a non-empty string"
        )
    return value


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise SyntheticKnxProtocolError("synthetic KNX event value_raw must be a string")
    return value


def _string_connection_value(
    connection: Mapping[str, object],
    key: str,
    *,
    default: str,
) -> str:
    value = connection.get(key, default)
    if not isinstance(value, str) or not value:
        raise SyntheticKnxProtocolError(f"source connection {key} must be a string")
    return value


def _int_connection_value(
    connection: Mapping[str, object],
    key: str,
    *,
    default: int,
) -> int:
    value = connection.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise SyntheticKnxProtocolError(f"source connection {key} must be an integer")
    return value

