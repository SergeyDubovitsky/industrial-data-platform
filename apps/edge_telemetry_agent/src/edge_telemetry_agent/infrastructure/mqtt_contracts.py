from __future__ import annotations

from collections.abc import Mapping

from edge_telemetry_agent.domain.events import TelemetryEvent, point_key_from_ref


def telemetry_topic(
    *,
    topic_root: str,
    asset_id: str,
    agent_id: str,
    source_id: str,
    point_ref: str,
) -> str:
    return (
        f"{topic_root}/assets/{asset_id}/agents/{agent_id}"
        f"/sources/{source_id}/points/{point_key_from_ref(point_ref)}/event"
    )


def telemetry_payload_from_event(event: TelemetryEvent) -> dict[str, object]:
    return {
        "message_type": "idp.edge.telemetry.event.v1",
        "tenant_id": event.tenant_id,
        "event_id": event.event_id,
        "event_type": event.event_type,
        "source_config_revision": event.source_config_revision,
        "ts": event.ts.isoformat().replace("+00:00", "Z"),
        "observation_mode": event.observation_mode,
        "value": event.value,
        "value_raw": event.value_raw,
        "quality": event.quality,
        "sequence": event.sequence,
    }


def telemetry_payload_from_canonical(payload: Mapping[str, object]) -> dict[str, object]:
    return {
        "message_type": "idp.edge.telemetry.event.v1",
        "tenant_id": _required_string(payload, "tenant_id"),
        "event_id": _required_string(payload, "event_id"),
        "event_type": _required_string(payload, "event_type"),
        "source_config_revision": _required_string(payload, "source_config_revision"),
        "ts": _required_string(payload, "ts"),
        "observation_mode": _required_string(payload, "observation_mode"),
        "value": payload.get("value"),
        "value_raw": payload.get("value_raw"),
        "quality": _required_string(payload, "quality"),
        "sequence": _required_int(payload, "sequence"),
    }


def _required_string(payload: Mapping[str, object], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Outbox payload field {field_name} must be a non-empty string")
    return value


def _required_int(payload: Mapping[str, object], field_name: str) -> int:
    value = payload.get(field_name)
    if not isinstance(value, int):
        raise ValueError(f"Outbox payload field {field_name} must be an integer")
    return value
