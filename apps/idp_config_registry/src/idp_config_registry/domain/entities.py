from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from idp_config_registry.domain.value_objects import (
    AgentStatus,
    AssetStatus,
    ConfigOutboxStatus,
    ConfigRevisionStatus,
    SignalType,
    TenantStatus,
    ValueType,
    require_non_empty,
    require_path_id,
    require_point_key,
)


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


@dataclass(frozen=True)
class Tenant:
    tenant_id: str
    name: str
    status: TenantStatus = TenantStatus.ACTIVE
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "tenant_id",
            require_non_empty(self.tenant_id, field_name="tenant_id"),
        )
        object.__setattr__(
            self,
            "name",
            require_non_empty(self.name, field_name="name"),
        )


@dataclass(frozen=True)
class Asset:
    tenant_id: str
    asset_id: str
    name: str
    description: str | None = None
    status: AssetStatus = AssetStatus.ACTIVE
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "tenant_id",
            require_non_empty(self.tenant_id, field_name="tenant_id"),
        )
        object.__setattr__(
            self,
            "asset_id",
            require_path_id(self.asset_id, field_name="asset_id"),
        )
        object.__setattr__(
            self,
            "name",
            require_non_empty(self.name, field_name="name"),
        )


@dataclass(frozen=True)
class Agent:
    tenant_id: str
    asset_id: str
    agent_id: str
    name: str | None = None
    status: AgentStatus = AgentStatus.ACTIVE
    bootstrap_hint_json: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "tenant_id",
            require_non_empty(self.tenant_id, field_name="tenant_id"),
        )
        object.__setattr__(
            self,
            "asset_id",
            require_path_id(self.asset_id, field_name="asset_id"),
        )
        object.__setattr__(
            self,
            "agent_id",
            require_path_id(self.agent_id, field_name="agent_id"),
        )


@dataclass(frozen=True)
class Source:
    tenant_id: str
    asset_id: str
    agent_id: str
    source_id: str
    source_type: str
    enabled: bool = True
    name: str | None = None
    description: str | None = None
    connection_json: dict[str, Any] = field(default_factory=dict)
    acquisition_defaults_json: dict[str, Any] = field(default_factory=dict)
    publish_defaults_json: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "tenant_id",
            require_non_empty(self.tenant_id, field_name="tenant_id"),
        )
        object.__setattr__(
            self,
            "asset_id",
            require_path_id(self.asset_id, field_name="asset_id"),
        )
        object.__setattr__(
            self,
            "agent_id",
            require_path_id(self.agent_id, field_name="agent_id"),
        )
        object.__setattr__(
            self,
            "source_id",
            require_path_id(self.source_id, field_name="source_id"),
        )
        object.__setattr__(
            self,
            "source_type",
            require_non_empty(self.source_type, field_name="source_type"),
        )


@dataclass(frozen=True)
class Point:
    tenant_id: str
    asset_id: str
    agent_id: str
    source_id: str
    point_id: str
    point_key: str
    point_ref: str
    name: str
    value_type: ValueType
    value_model: str
    signal_type: SignalType
    description: str | None = None
    unit: str | None = None
    enabled: bool = True
    acquisition_json: dict[str, Any] = field(default_factory=dict)
    publish_json: dict[str, Any] = field(default_factory=dict)
    tags_json: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "tenant_id",
            require_non_empty(self.tenant_id, field_name="tenant_id"),
        )
        object.__setattr__(
            self,
            "asset_id",
            require_path_id(self.asset_id, field_name="asset_id"),
        )
        object.__setattr__(
            self,
            "agent_id",
            require_path_id(self.agent_id, field_name="agent_id"),
        )
        object.__setattr__(
            self,
            "source_id",
            require_path_id(self.source_id, field_name="source_id"),
        )
        object.__setattr__(
            self,
            "point_id",
            require_non_empty(self.point_id, field_name="point_id"),
        )
        object.__setattr__(self, "point_key", require_point_key(self.point_key))
        object.__setattr__(
            self,
            "point_ref",
            require_non_empty(self.point_ref, field_name="point_ref"),
        )
        object.__setattr__(
            self,
            "name",
            require_non_empty(self.name, field_name="name"),
        )
        object.__setattr__(
            self,
            "value_model",
            require_non_empty(self.value_model, field_name="value_model"),
        )


@dataclass(frozen=True)
class AgentRuntimeConfigRevision:
    tenant_id: str
    asset_id: str
    agent_id: str
    config_revision: str
    issued_at: datetime
    agent_runtime_payload_json: dict[str, Any]
    status: ConfigRevisionStatus = ConfigRevisionStatus.RENDERED
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "tenant_id",
            require_non_empty(self.tenant_id, field_name="tenant_id"),
        )
        object.__setattr__(
            self,
            "asset_id",
            require_path_id(self.asset_id, field_name="asset_id"),
        )
        object.__setattr__(
            self,
            "agent_id",
            require_path_id(self.agent_id, field_name="agent_id"),
        )
        object.__setattr__(
            self,
            "config_revision",
            require_non_empty(self.config_revision, field_name="config_revision"),
        )


@dataclass(frozen=True)
class SourceConfigRevision:
    tenant_id: str
    asset_id: str
    agent_id: str
    source_id: str
    source_config_revision: str
    config_revision: str
    issued_at: datetime
    source_payload_json: dict[str, Any]
    status: ConfigRevisionStatus = ConfigRevisionStatus.RENDERED
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "tenant_id",
            require_non_empty(self.tenant_id, field_name="tenant_id"),
        )
        object.__setattr__(
            self,
            "asset_id",
            require_path_id(self.asset_id, field_name="asset_id"),
        )
        object.__setattr__(
            self,
            "agent_id",
            require_path_id(self.agent_id, field_name="agent_id"),
        )
        object.__setattr__(
            self,
            "source_id",
            require_path_id(self.source_id, field_name="source_id"),
        )
        object.__setattr__(
            self,
            "source_config_revision",
            require_non_empty(
                self.source_config_revision,
                field_name="source_config_revision",
            ),
        )
        object.__setattr__(
            self,
            "config_revision",
            require_non_empty(self.config_revision, field_name="config_revision"),
        )


@dataclass(frozen=True)
class ConfigOutboxRecord:
    tenant_id: str
    outbox_id: UUID
    idempotency_key: str
    asset_id: str
    agent_id: str
    config_revision: str
    config_scope: str
    source_id: str | None
    source_config_revision: str | None
    message_type: str
    kafka_topic: str
    kafka_key: str
    payload_json: dict[str, Any]
    status: ConfigOutboxStatus = ConfigOutboxStatus.PENDING
    available_at: datetime = field(default_factory=utc_now)
    lease_expires_at: datetime | None = None
    published_at: datetime | None = None
    attempt_count: int = 0
    next_attempt_at: datetime | None = None
    last_error: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    @classmethod
    def new(
        cls,
        *,
        tenant_id: str,
        idempotency_key: str,
        asset_id: str,
        agent_id: str,
        config_revision: str,
        config_scope: str,
        source_id: str | None,
        source_config_revision: str | None,
        kafka_key: str,
        payload_json: dict[str, Any],
    ) -> ConfigOutboxRecord:
        return cls(
            tenant_id=tenant_id,
            outbox_id=uuid4(),
            idempotency_key=idempotency_key,
            asset_id=asset_id,
            agent_id=agent_id,
            config_revision=config_revision,
            config_scope=config_scope,
            source_id=source_id,
            source_config_revision=source_config_revision,
            message_type="idp.edge.config.delivery.v1",
            kafka_topic="idp.edge.configs.v1",
            kafka_key=kafka_key,
            payload_json=payload_json,
        )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "tenant_id",
            require_non_empty(self.tenant_id, field_name="tenant_id"),
        )
        object.__setattr__(
            self,
            "idempotency_key",
            require_non_empty(self.idempotency_key, field_name="idempotency_key"),
        )
        object.__setattr__(
            self,
            "asset_id",
            require_path_id(self.asset_id, field_name="asset_id"),
        )
        object.__setattr__(
            self,
            "agent_id",
            require_path_id(self.agent_id, field_name="agent_id"),
        )
        object.__setattr__(
            self,
            "config_revision",
            require_non_empty(self.config_revision, field_name="config_revision"),
        )
        object.__setattr__(
            self,
            "config_scope",
            require_non_empty(self.config_scope, field_name="config_scope"),
        )

    def reserve(self, *, now: datetime, lease_duration: timedelta) -> ConfigOutboxRecord:
        return self._replace(
            status=ConfigOutboxStatus.INFLIGHT,
            lease_expires_at=now + lease_duration,
            updated_at=now,
        )

    def mark_published(self, *, now: datetime) -> ConfigOutboxRecord:
        return self._replace(
            status=ConfigOutboxStatus.PUBLISHED,
            lease_expires_at=None,
            published_at=now,
            updated_at=now,
        )

    def mark_retry(
        self,
        *,
        now: datetime,
        error: str,
        next_attempt_at: datetime,
    ) -> ConfigOutboxRecord:
        return self._replace(
            status=ConfigOutboxStatus.RETRY,
            lease_expires_at=None,
            attempt_count=self.attempt_count + 1,
            next_attempt_at=next_attempt_at,
            last_error=error,
            updated_at=now,
        )

    def mark_dead_letter(
        self,
        *,
        now: datetime,
        error: str,
    ) -> ConfigOutboxRecord:
        return self._replace(
            status=ConfigOutboxStatus.DEAD_LETTER,
            lease_expires_at=None,
            attempt_count=self.attempt_count + 1,
            last_error=error,
            updated_at=now,
        )

    def release_expired_lease(self, *, now: datetime) -> ConfigOutboxRecord:
        return self._replace(
            status=ConfigOutboxStatus.RETRY,
            lease_expires_at=None,
            next_attempt_at=now,
            updated_at=now,
        )

    def _replace(self, **changes: object) -> ConfigOutboxRecord:
        values = {
            "tenant_id": self.tenant_id,
            "outbox_id": self.outbox_id,
            "idempotency_key": self.idempotency_key,
            "asset_id": self.asset_id,
            "agent_id": self.agent_id,
            "config_revision": self.config_revision,
            "config_scope": self.config_scope,
            "source_id": self.source_id,
            "source_config_revision": self.source_config_revision,
            "message_type": self.message_type,
            "kafka_topic": self.kafka_topic,
            "kafka_key": self.kafka_key,
            "payload_json": self.payload_json,
            "status": self.status,
            "available_at": self.available_at,
            "lease_expires_at": self.lease_expires_at,
            "published_at": self.published_at,
            "attempt_count": self.attempt_count,
            "next_attempt_at": self.next_attempt_at,
            "last_error": self.last_error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        values.update(changes)
        return ConfigOutboxRecord(**values)
