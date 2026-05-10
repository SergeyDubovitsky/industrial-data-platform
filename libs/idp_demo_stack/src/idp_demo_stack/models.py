from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BrokerConfig:
    host: str
    port: int


@dataclass(frozen=True)
class KafkaConfig:
    bootstrap_servers: str
    client_id: str


@dataclass(frozen=True)
class ConfigRegistryConfig:
    base_url: str
    timeout_seconds: float = 30.0


@dataclass(frozen=True)
class TopicScope:
    topic_root: str
    asset_id: str
    agent_id: str

    def agent_runtime_config_topic(self) -> str:
        return f"{self.topic_root}/agents/{self.agent_id}/config/agent-runtime"

    def source_config_topic(self, source_id: str) -> str:
        return f"{self.topic_root}/agents/{self.agent_id}/sources/{source_id}/config"

    def point_topic(self, source_id: str, point_key: str, suffix: str) -> str:
        return (
            f"{self.topic_root}/assets/{self.asset_id}/agents/{self.agent_id}"
            f"/sources/{source_id}/points/{point_key}/{suffix}"
        )

    def source_status_topic(self, source_id: str) -> str:
        return (
            f"{self.topic_root}/assets/{self.asset_id}/agents/{self.agent_id}"
            f"/sources/{source_id}/status/connection"
        )

    def agent_lwt_topic(self) -> str:
        return (
            f"{self.topic_root}/assets/{self.asset_id}/agents/{self.agent_id}"
            f"/status/lwt"
        )


@dataclass(frozen=True)
class BundlePoint:
    point_key: str
    point_ref: str
    name: str
    description: str | None
    signal_type: str
    value_type: str
    value_model: str
    unit: str | None
    acquisition: dict[str, Any]
    publish: dict[str, Any]
    tags: dict[str, str]

    def source_config_entry(self) -> dict[str, Any]:
        return {
            "point_key": self.point_key,
            "point_ref": self.point_ref,
            "name": self.name,
            "description": self.description,
            "signal_type": self.signal_type,
            "value_type": self.value_type,
            "value_model": self.value_model,
            "unit": self.unit,
            "acquisition": dict(self.acquisition),
            "publish": dict(self.publish),
            "tags": dict(self.tags),
        }


@dataclass(frozen=True)
class BundleSource:
    source_id: str
    source_config_revision: str
    source_type: str
    enabled: bool
    connection: dict[str, Any]
    acquisition_defaults: dict[str, Any]
    publish_defaults: dict[str, Any]
    points: tuple[BundlePoint, ...]


@dataclass(frozen=True)
class ConfigBundle:
    tenant_id: str
    asset_id: str
    agent_id: str
    config_revision: str
    issued_at: str
    sources: tuple[BundleSource, ...]

    def source(self, source_id: str | None) -> BundleSource:
        if source_id is None:
            for source in self.sources:
                if source.enabled:
                    return source
            raise ValueError("Bundle does not contain an enabled source")
        for source in self.sources:
            if source.source_id == source_id:
                return source
        raise ValueError(f"Bundle does not contain source_id={source_id}")


@dataclass(frozen=True)
class WaveConfig:
    base: float
    amplitude: float
    period: float


@dataclass(frozen=True)
class DemoSettings:
    broker: BrokerConfig
    kafka: KafkaConfig
    idp_config_registry: ConfigRegistryConfig
    username: str | None
    password: str | None
    client_id: str
    scope: TopicScope
    bundle: ConfigBundle
    telemetry_source_id: str
    interval_seconds: float
    count: int
    temperature: WaveConfig
    config_delivery: str
    publish_config: bool
    publish_status: bool
    retained_refresh_seconds: float


@dataclass(frozen=True)
class PublishMessage:
    topic: str
    payload: dict[str, Any]
    qos: int = 1
    retain: bool = False


@dataclass(frozen=True)
class KafkaRecord:
    topic: str
    key: str
    payload: dict[str, Any]
