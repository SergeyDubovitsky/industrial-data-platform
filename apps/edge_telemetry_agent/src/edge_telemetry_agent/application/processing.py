from __future__ import annotations

from datetime import datetime
from typing import Protocol

from edge_telemetry_agent.domain.config import AgentRuntimeConfig, RuntimePoint
from edge_telemetry_agent.domain.events import Observation, Quality, TelemetryEvent
from edge_telemetry_agent.modeling import EdgeModel, FrozenEdgeModel


class PointState(EdgeModel):
    last_observed_value: object | None = None
    last_observed_at: datetime | None = None
    last_observed_raw: str | None = None
    last_observed_quality: Quality | None = None
    last_published_value: object | None = None
    last_published_at: datetime | None = None
    last_published_raw: str | None = None
    last_published_quality: Quality | None = None
    published_count: int = 0


class ProcessingResult(FrozenEdgeModel):
    event: TelemetryEvent | None
    suppressed_reason: str | None = None


class PointStateStore(Protocol):
    def get(self, source_id: str, point_ref: str) -> PointState | None:
        ...

    def save(self, source_id: str, point_ref: str, state: PointState) -> None:
        ...


class ObservationProcessor:
    def __init__(
        self,
        runtime_config: AgentRuntimeConfig,
        agent_id: str,
        *,
        state_store: PointStateStore | None = None,
    ) -> None:
        self._runtime_config = runtime_config
        self._agent_id = agent_id
        self._state_store = state_store
        self._states: dict[tuple[str, str], PointState] = {}

    def process(self, observation: Observation) -> ProcessingResult:
        point = self._runtime_config.point(observation.source_id, observation.point_ref)
        state = self._state_for(observation.source_id, observation.point_ref)
        state.last_observed_value = observation.value
        state.last_observed_at = observation.observed_at
        state.last_observed_raw = observation.value_raw
        state.last_observed_quality = observation.quality
        if point.signal_type == "command":
            self._save_state(observation.source_id, observation.point_ref, state)
            return ProcessingResult(event=None, suppressed_reason="command_point")
        if not point.publish.enabled:
            self._save_state(observation.source_id, observation.point_ref, state)
            return ProcessingResult(event=None, suppressed_reason="publish_disabled")
        if not self._should_publish(point, state.last_published_value, observation.value):
            self._save_state(observation.source_id, observation.point_ref, state)
            return ProcessingResult(event=None, suppressed_reason="not_significant")

        state.published_count += 1
        state.last_published_value = observation.value
        state.last_published_at = observation.observed_at
        state.last_published_raw = observation.value_raw
        state.last_published_quality = observation.quality
        self._save_state(observation.source_id, observation.point_ref, state)
        event = TelemetryEvent.new(
            event_type=_event_type_for(point),
            agent_id=self._agent_id,
            tenant_id=self._runtime_config.tenant_id,
            asset_id=self._runtime_config.asset_id,
            source_id=point.source_id,
            source_type=point.source_type,
            source_config_revision=point.source_config_revision,
            point_ref=point.point_ref,
            name=point.name,
            description=point.description,
            value_type=point.value_type,
            value_model=point.value_model,
            signal_type=point.signal_type,
            observation_mode=observation.observation_mode,
            value=observation.value,
            value_raw=observation.value_raw,
            quality=observation.quality,
            sequence=state.published_count,
            unit=point.unit,
            tags=dict(point.tags),
            ts=observation.observed_at,
        )
        return ProcessingResult(event=event)

    def _state_for(self, source_id: str, point_ref: str) -> PointState:
        key = (source_id, point_ref)
        existing = self._states.get(key)
        if existing is not None:
            return existing
        persisted = self._state_store.get(source_id, point_ref) if self._state_store else None
        state = persisted or PointState()
        self._states[key] = state
        return state

    def _save_state(self, source_id: str, point_ref: str, state: PointState) -> None:
        if self._state_store is not None:
            self._state_store.save(source_id, point_ref, state)

    def _should_publish(
        self,
        point: RuntimePoint,
        previous_value: object | None,
        current_value: object | None,
    ) -> bool:
        if previous_value is None:
            return True
        if point.publish.change_threshold is None:
            return current_value != previous_value
        previous_number = _as_number(previous_value)
        current_number = _as_number(current_value)
        if previous_number is None or current_number is None:
            return current_value != previous_value
        return abs(current_number - previous_number) >= point.publish.change_threshold


def _event_type_for(point: RuntimePoint) -> str:
    if point.value_type == "number":
        return "telemetry.sample"
    return "telemetry.changed"


def _as_number(value: object | None) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)
