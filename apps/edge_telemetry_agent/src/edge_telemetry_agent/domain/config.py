from __future__ import annotations

from pathlib import Path
from typing import Literal

from edge_telemetry_agent.modeling import FrozenEdgeModel

ValueType = Literal["boolean", "number", "string"]
SignalType = Literal["command", "feedback", "status", "sensor"]


class ConfigurationError(ValueError):
    """Raised when the agent runtime configuration is invalid."""


class AcquisitionSettings(FrozenEdgeModel):
    listen: bool = True
    read_on_start: bool = False
    periodic_interval_seconds: float | None = None


class PublishSettings(FrozenEdgeModel):
    enabled: bool = True
    change_threshold: float | None = None


class MqttSettings(FrozenEdgeModel):
    enabled: bool
    version: str
    broker: str
    topic_root: str
    client_id_prefix: str
    username_env: str | None
    password_env: str | None
    qos: int
    clean_start: bool
    session_expiry_seconds: int
    telemetry_message_expiry_seconds: int
    connect_timeout_seconds: int
    retry_backoff_seconds: tuple[int, ...]


class DeliverySettings(FrozenEdgeModel):
    transport: str
    mqtt: MqttSettings | None = None


class StorageSettings(FrozenEdgeModel):
    sqlite_path: Path
    retention_days: int
    dead_letter_after_attempts: int


class ObservabilitySettings(FrozenEdgeModel):
    log_level: str
    emit_health_events: bool
    metrics_bind: str | None


class BootstrapConfig(FrozenEdgeModel):
    agent_id: str
    delivery: DeliverySettings
    storage: StorageSettings
    observability: ObservabilitySettings


class SourceRuntimeRef(FrozenEdgeModel):
    source_id: str
    source_config_revision: str
    enabled: bool


class SourceDefinition(FrozenEdgeModel):
    source_id: str
    source_config_revision: str
    source_type: str
    enabled: bool
    connection: dict[str, object]
    acquisition_defaults: AcquisitionSettings
    publish_defaults: PublishSettings


class RuntimePoint(FrozenEdgeModel):
    source_id: str
    source_type: str
    source_config_revision: str
    point_key: str
    point_ref: str
    name: str
    description: str | None
    value_type: ValueType
    value_model: str
    signal_type: SignalType
    unit: str | None
    acquisition: AcquisitionSettings
    publish: PublishSettings
    tags: dict[str, str]


class AgentRuntimeConfig(FrozenEdgeModel):
    tenant_id: str
    asset_id: str
    agent_id: str
    config_revision: str
    delivery: DeliverySettings
    storage: StorageSettings
    observability: ObservabilitySettings
    sources: dict[str, SourceDefinition]
    source_refs: dict[str, SourceRuntimeRef]
    points: dict[tuple[str, str], RuntimePoint]

    def point(self, source_id: str, point_ref: str) -> RuntimePoint:
        return self.points[(source_id, point_ref)]


class ConfigStatusMessage(FrozenEdgeModel):
    agent_id: str
    status: Literal["pending", "applied", "rejected"]
    ts: str
    tenant_id: str | None = None
    asset_id: str | None = None
    config_revision: str | None = None
    reason: str | None = None

    def topic(self, topic_root: str) -> str:
        return f"{topic_root}/agents/{self.agent_id}/status/config"

    def mqtt_payload(self) -> dict[str, object]:
        return self.model_dump(mode="json") | {"message_type": "idp.edge.config.status.v1"}
