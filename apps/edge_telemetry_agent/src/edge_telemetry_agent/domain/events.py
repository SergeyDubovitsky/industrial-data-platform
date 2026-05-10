from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from urllib.parse import quote
from uuid import uuid4

from pydantic import Field

from edge_telemetry_agent.modeling import FrozenEdgeModel

EventType = Literal["telemetry.changed", "telemetry.sample"]
ObservationMode = Literal["listen", "read_on_start", "periodic_read"]
Quality = Literal["good", "uncertain", "bad"]
# MVP intentionally limits telemetry values to scalars. Complex protocol values
# like OPC UA arrays/structures require a separate future wire contract.
ScalarValue = bool | int | float | str


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def isoformat_utc(value: datetime) -> str:
    normalized = value.astimezone(UTC).replace(microsecond=0)
    return normalized.isoformat().replace("+00:00", "Z")


def point_key_from_ref(point_ref: str) -> str:
    return quote(point_ref, safe="")


class Observation(FrozenEdgeModel):
    source_id: str
    point_ref: str
    observation_mode: ObservationMode
    value: ScalarValue | None
    observed_at: datetime = Field(default_factory=utc_now)
    value_raw: str | None = None
    quality: Quality = "good"


class TelemetryEvent(FrozenEdgeModel):
    event_type: EventType
    event_id: str
    ts: datetime
    agent_id: str
    tenant_id: str
    asset_id: str
    source_id: str
    source_type: str
    source_config_revision: str
    point_ref: str
    name: str
    description: str | None
    value_type: str
    value_model: str
    signal_type: str
    observation_mode: ObservationMode
    value: ScalarValue | None
    value_raw: str | None
    quality: Quality
    sequence: int
    unit: str | None
    tags: dict[str, str]

    @property
    def point_key(self) -> str:
        return point_key_from_ref(self.point_ref)

    @classmethod
    def new(
        cls,
        *,
        event_type: EventType,
        agent_id: str,
        tenant_id: str,
        asset_id: str,
        source_id: str,
        source_type: str,
        source_config_revision: str,
        point_ref: str,
        name: str,
        description: str | None,
        value_type: str,
        value_model: str,
        signal_type: str,
        observation_mode: ObservationMode,
        value: ScalarValue | None,
        value_raw: str | None,
        quality: Quality,
        sequence: int,
        unit: str | None,
        tags: dict[str, str],
        ts: datetime | None = None,
    ) -> "TelemetryEvent":
        return cls(
            event_type=event_type,
            event_id=uuid4().hex,
            ts=ts or utc_now(),
            agent_id=agent_id,
            tenant_id=tenant_id,
            asset_id=asset_id,
            source_id=source_id,
            source_type=source_type,
            source_config_revision=source_config_revision,
            point_ref=point_ref,
            name=name,
            description=description,
            value_type=value_type,
            value_model=value_model,
            signal_type=signal_type,
            observation_mode=observation_mode,
            value=value,
            value_raw=value_raw,
            quality=quality,
            sequence=sequence,
            unit=unit,
            tags=tags,
        )

    def canonical_payload(self) -> dict[str, object]:
        return {
            "event_type": self.event_type,
            "event_id": self.event_id,
            "ts": isoformat_utc(self.ts),
            "agent_id": self.agent_id,
            "tenant_id": self.tenant_id,
            "asset_id": self.asset_id,
            "source_id": self.source_id,
            "source_type": self.source_type,
            "source_config_revision": self.source_config_revision,
            "point_ref": self.point_ref,
            "name": self.name,
            "description": self.description,
            "value_type": self.value_type,
            "value_model": self.value_model,
            "signal_type": self.signal_type,
            "observation_mode": self.observation_mode,
            "value": self.value,
            "value_raw": self.value_raw,
            "quality": self.quality,
            "sequence": self.sequence,
            "unit": self.unit,
            "tags": self.tags,
        }


class MqttPublication(FrozenEdgeModel):
    topic: str
    payload: dict[str, object]
    qos: int
    retain: bool
    message_expiry_seconds: int | None = None
