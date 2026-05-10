from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from types import TracebackType
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from idp_config_registry.domain.entities import (
    Agent,
    AgentRuntimeConfigRevision,
    Asset,
    ConfigOutboxRecord,
    Point,
    Source,
    SourceConfigRevision,
    Tenant,
)
from idp_config_registry.domain.value_objects import (
    AgentStatus,
    AssetStatus,
    ConfigOutboxStatus,
    ConfigRevisionStatus,
    SignalType,
    TenantStatus,
    ValueType,
)
from idp_config_registry.infrastructure.postgres.database import PostgresSessionManager
from idp_config_registry.infrastructure.postgres.models import (
    AgentModel,
    AgentRuntimeConfigRevisionModel,
    AssetModel,
    ConfigOutboxModel,
    PointModel,
    SourceConfigRevisionModel,
    SourceModel,
    TenantModel,
)


def _tenant_to_model(tenant: Tenant) -> TenantModel:
    return TenantModel(
        tenant_id=tenant.tenant_id,
        name=tenant.name,
        status=tenant.status.value,
        created_at=tenant.created_at,
        updated_at=tenant.updated_at,
    )


def _tenant_from_model(model: TenantModel) -> Tenant:
    return Tenant(
        tenant_id=model.tenant_id,
        name=model.name,
        status=TenantStatus(model.status),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _asset_to_model(asset: Asset) -> AssetModel:
    return AssetModel(
        tenant_id=asset.tenant_id,
        asset_id=asset.asset_id,
        name=asset.name,
        description=asset.description,
        status=asset.status.value,
        created_at=asset.created_at,
        updated_at=asset.updated_at,
    )


def _asset_from_model(model: AssetModel) -> Asset:
    return Asset(
        tenant_id=model.tenant_id,
        asset_id=model.asset_id,
        name=model.name,
        description=model.description,
        status=AssetStatus(model.status),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _agent_to_model(agent: Agent) -> AgentModel:
    return AgentModel(
        tenant_id=agent.tenant_id,
        asset_id=agent.asset_id,
        agent_id=agent.agent_id,
        name=agent.name,
        status=agent.status.value,
        bootstrap_hint_json=dict(agent.bootstrap_hint_json),
        created_at=agent.created_at,
        updated_at=agent.updated_at,
    )


def _agent_from_model(model: AgentModel) -> Agent:
    return Agent(
        tenant_id=model.tenant_id,
        asset_id=model.asset_id,
        agent_id=model.agent_id,
        name=model.name,
        status=AgentStatus(model.status),
        bootstrap_hint_json=dict(model.bootstrap_hint_json),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _source_to_model(source: Source) -> SourceModel:
    return SourceModel(
        tenant_id=source.tenant_id,
        asset_id=source.asset_id,
        agent_id=source.agent_id,
        source_id=source.source_id,
        source_type=source.source_type,
        enabled=source.enabled,
        name=source.name,
        description=source.description,
        connection_json=dict(source.connection_json),
        acquisition_defaults_json=dict(source.acquisition_defaults_json),
        publish_defaults_json=dict(source.publish_defaults_json),
        created_at=source.created_at,
        updated_at=source.updated_at,
    )


def _source_from_model(model: SourceModel) -> Source:
    return Source(
        tenant_id=model.tenant_id,
        asset_id=model.asset_id,
        agent_id=model.agent_id,
        source_id=model.source_id,
        source_type=model.source_type,
        enabled=model.enabled,
        name=model.name,
        description=model.description,
        connection_json=dict(model.connection_json),
        acquisition_defaults_json=dict(model.acquisition_defaults_json),
        publish_defaults_json=dict(model.publish_defaults_json),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _point_to_model(point: Point) -> PointModel:
    return PointModel(
        tenant_id=point.tenant_id,
        asset_id=point.asset_id,
        agent_id=point.agent_id,
        source_id=point.source_id,
        point_id=point.point_id,
        point_key=point.point_key,
        point_ref=point.point_ref,
        name=point.name,
        description=point.description,
        value_type=point.value_type.value,
        value_model=point.value_model,
        signal_type=point.signal_type.value,
        unit=point.unit,
        enabled=point.enabled,
        acquisition_json=dict(point.acquisition_json),
        publish_json=dict(point.publish_json),
        tags_json=dict(point.tags_json),
        created_at=point.created_at,
        updated_at=point.updated_at,
    )


def _point_from_model(model: PointModel) -> Point:
    return Point(
        tenant_id=model.tenant_id,
        asset_id=model.asset_id,
        agent_id=model.agent_id,
        source_id=model.source_id,
        point_id=model.point_id,
        point_key=model.point_key,
        point_ref=model.point_ref,
        name=model.name,
        description=model.description,
        value_type=ValueType(model.value_type),
        value_model=model.value_model,
        signal_type=SignalType(model.signal_type),
        unit=model.unit,
        enabled=model.enabled,
        acquisition_json=dict(model.acquisition_json),
        publish_json=dict(model.publish_json),
        tags_json=dict(model.tags_json),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _agent_runtime_config_revision_to_model(
    revision: AgentRuntimeConfigRevision,
) -> AgentRuntimeConfigRevisionModel:
    return AgentRuntimeConfigRevisionModel(
        tenant_id=revision.tenant_id,
        asset_id=revision.asset_id,
        agent_id=revision.agent_id,
        config_revision=revision.config_revision,
        status=revision.status.value,
        issued_at=revision.issued_at,
        agent_runtime_payload_json=dict(revision.agent_runtime_payload_json),
        created_at=revision.created_at,
    )


def _agent_runtime_config_revision_from_model(
    model: AgentRuntimeConfigRevisionModel,
) -> AgentRuntimeConfigRevision:
    return AgentRuntimeConfigRevision(
        tenant_id=model.tenant_id,
        asset_id=model.asset_id,
        agent_id=model.agent_id,
        config_revision=model.config_revision,
        status=ConfigRevisionStatus(model.status),
        issued_at=model.issued_at,
        agent_runtime_payload_json=dict(model.agent_runtime_payload_json),
        created_at=model.created_at,
    )


def _source_config_revision_to_model(
    revision: SourceConfigRevision,
) -> SourceConfigRevisionModel:
    return SourceConfigRevisionModel(
        tenant_id=revision.tenant_id,
        asset_id=revision.asset_id,
        agent_id=revision.agent_id,
        source_id=revision.source_id,
        source_config_revision=revision.source_config_revision,
        config_revision=revision.config_revision,
        status=revision.status.value,
        issued_at=revision.issued_at,
        source_payload_json=dict(revision.source_payload_json),
        created_at=revision.created_at,
    )


def _source_config_revision_from_model(
    model: SourceConfigRevisionModel,
) -> SourceConfigRevision:
    return SourceConfigRevision(
        tenant_id=model.tenant_id,
        asset_id=model.asset_id,
        agent_id=model.agent_id,
        source_id=model.source_id,
        source_config_revision=model.source_config_revision,
        config_revision=model.config_revision,
        status=ConfigRevisionStatus(model.status),
        issued_at=model.issued_at,
        source_payload_json=dict(model.source_payload_json),
        created_at=model.created_at,
    )


def _config_outbox_to_model(record: ConfigOutboxRecord) -> ConfigOutboxModel:
    return ConfigOutboxModel(
        tenant_id=record.tenant_id,
        outbox_id=record.outbox_id,
        idempotency_key=record.idempotency_key,
        asset_id=record.asset_id,
        agent_id=record.agent_id,
        config_revision=record.config_revision,
        config_scope=record.config_scope,
        source_id=record.source_id,
        source_config_revision=record.source_config_revision,
        message_type=record.message_type,
        kafka_topic=record.kafka_topic,
        kafka_key=record.kafka_key,
        payload_json=dict(record.payload_json),
        status=record.status.value,
        available_at=record.available_at,
        lease_expires_at=record.lease_expires_at,
        published_at=record.published_at,
        attempt_count=record.attempt_count,
        next_attempt_at=record.next_attempt_at,
        last_error=record.last_error,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _config_outbox_from_model(model: ConfigOutboxModel) -> ConfigOutboxRecord:
    return ConfigOutboxRecord(
        tenant_id=model.tenant_id,
        outbox_id=model.outbox_id,
        idempotency_key=model.idempotency_key,
        asset_id=model.asset_id,
        agent_id=model.agent_id,
        config_revision=model.config_revision,
        config_scope=model.config_scope,
        source_id=model.source_id,
        source_config_revision=model.source_config_revision,
        message_type=model.message_type,
        kafka_topic=model.kafka_topic,
        kafka_key=model.kafka_key,
        payload_json=dict(model.payload_json),
        status=ConfigOutboxStatus(model.status),
        available_at=model.available_at,
        lease_expires_at=model.lease_expires_at,
        published_at=model.published_at,
        attempt_count=model.attempt_count,
        next_attempt_at=model.next_attempt_at,
        last_error=model.last_error,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


@dataclass
class PostgresTenantRepository:
    session: AsyncSession

    async def add(self, tenant: Tenant) -> None:
        self.session.add(_tenant_to_model(tenant))

    async def get(self, tenant_id: str) -> Tenant | None:
        model = await self.session.get(TenantModel, tenant_id)
        return _tenant_from_model(model) if model is not None else None

    async def update(self, tenant: Tenant) -> None:
        await self.session.merge(_tenant_to_model(tenant))
        await self.session.flush()

    async def delete(self, tenant_id: str) -> None:
        model = await self.session.get(TenantModel, tenant_id)
        if model is not None:
            await self.session.delete(model)
            await self.session.flush()

    async def list(self) -> list[Tenant]:
        result = await self.session.scalars(
            select(TenantModel).order_by(TenantModel.tenant_id)
        )
        return [_tenant_from_model(model) for model in result]


@dataclass
class PostgresAssetRepository:
    session: AsyncSession

    async def add(self, asset: Asset) -> None:
        self.session.add(_asset_to_model(asset))

    async def get(self, tenant_id: str, asset_id: str) -> Asset | None:
        model = await self.session.get(AssetModel, (tenant_id, asset_id))
        return _asset_from_model(model) if model is not None else None

    async def update(self, asset: Asset) -> None:
        await self.session.merge(_asset_to_model(asset))
        await self.session.flush()

    async def delete(self, tenant_id: str, asset_id: str) -> None:
        model = await self.session.get(AssetModel, (tenant_id, asset_id))
        if model is not None:
            await self.session.delete(model)
            await self.session.flush()

    async def list_for_tenant(self, tenant_id: str) -> list[Asset]:
        result = await self.session.scalars(
            select(AssetModel)
            .where(AssetModel.tenant_id == tenant_id)
            .order_by(AssetModel.asset_id)
        )
        return [_asset_from_model(model) for model in result]


@dataclass
class PostgresAgentRepository:
    session: AsyncSession

    async def add(self, agent: Agent) -> None:
        self.session.add(_agent_to_model(agent))

    async def get(self, tenant_id: str, asset_id: str, agent_id: str) -> Agent | None:
        model = await self.session.get(AgentModel, (tenant_id, asset_id, agent_id))
        return _agent_from_model(model) if model is not None else None

    async def update(self, agent: Agent) -> None:
        await self.session.merge(_agent_to_model(agent))
        await self.session.flush()

    async def delete(self, tenant_id: str, asset_id: str, agent_id: str) -> None:
        model = await self.session.get(AgentModel, (tenant_id, asset_id, agent_id))
        if model is not None:
            await self.session.delete(model)
            await self.session.flush()

    async def list_for_asset(self, tenant_id: str, asset_id: str) -> list[Agent]:
        result = await self.session.scalars(
            select(AgentModel)
            .where(
                AgentModel.tenant_id == tenant_id,
                AgentModel.asset_id == asset_id,
            )
            .order_by(AgentModel.agent_id)
        )
        return [_agent_from_model(model) for model in result]


@dataclass
class PostgresSourceRepository:
    session: AsyncSession

    async def add(self, source: Source) -> None:
        self.session.add(_source_to_model(source))

    async def get(
        self,
        tenant_id: str,
        asset_id: str,
        agent_id: str,
        source_id: str,
    ) -> Source | None:
        model = await self.session.get(
            SourceModel,
            (tenant_id, asset_id, agent_id, source_id),
        )
        return _source_from_model(model) if model is not None else None

    async def update(self, source: Source) -> None:
        await self.session.merge(_source_to_model(source))
        await self.session.flush()

    async def delete(
        self,
        tenant_id: str,
        asset_id: str,
        agent_id: str,
        source_id: str,
    ) -> None:
        model = await self.session.get(
            SourceModel,
            (tenant_id, asset_id, agent_id, source_id),
        )
        if model is not None:
            await self.session.delete(model)
            await self.session.flush()

    async def list_for_agent(
        self,
        tenant_id: str,
        asset_id: str,
        agent_id: str,
    ) -> list[Source]:
        result = await self.session.scalars(
            select(SourceModel)
            .where(
                SourceModel.tenant_id == tenant_id,
                SourceModel.asset_id == asset_id,
                SourceModel.agent_id == agent_id,
            )
            .order_by(SourceModel.source_id)
        )
        return [_source_from_model(model) for model in result]


@dataclass
class PostgresPointRepository:
    session: AsyncSession

    async def add(self, point: Point) -> None:
        self.session.add(_point_to_model(point))

    async def get_by_id(self, tenant_id: str, point_id: str) -> Point | None:
        model = await self.session.get(PointModel, (tenant_id, point_id))
        return _point_from_model(model) if model is not None else None

    async def update(self, point: Point) -> None:
        await self.session.merge(_point_to_model(point))
        await self.session.flush()

    async def delete(self, tenant_id: str, point_id: str) -> None:
        model = await self.session.get(PointModel, (tenant_id, point_id))
        if model is not None:
            await self.session.delete(model)
            await self.session.flush()

    async def get_by_key(
        self,
        tenant_id: str,
        asset_id: str,
        agent_id: str,
        source_id: str,
        point_key: str,
    ) -> Point | None:
        result = await self.session.scalars(
            select(PointModel).where(
                PointModel.tenant_id == tenant_id,
                PointModel.asset_id == asset_id,
                PointModel.agent_id == agent_id,
                PointModel.source_id == source_id,
                PointModel.point_key == point_key,
            )
        )
        model = result.first()
        return _point_from_model(model) if model is not None else None

    async def get_by_ref(
        self,
        tenant_id: str,
        asset_id: str,
        agent_id: str,
        source_id: str,
        point_ref: str,
    ) -> Point | None:
        result = await self.session.scalars(
            select(PointModel).where(
                PointModel.tenant_id == tenant_id,
                PointModel.asset_id == asset_id,
                PointModel.agent_id == agent_id,
                PointModel.source_id == source_id,
                PointModel.point_ref == point_ref,
            )
        )
        model = result.first()
        return _point_from_model(model) if model is not None else None

    async def list_for_source(
        self,
        tenant_id: str,
        asset_id: str,
        agent_id: str,
        source_id: str,
    ) -> list[Point]:
        result = await self.session.scalars(
            select(PointModel)
            .where(
                PointModel.tenant_id == tenant_id,
                PointModel.asset_id == asset_id,
                PointModel.agent_id == agent_id,
                PointModel.source_id == source_id,
            )
            .order_by(PointModel.point_key)
        )
        return [_point_from_model(model) for model in result]


@dataclass
class PostgresAgentRuntimeConfigRevisionRepository:
    session: AsyncSession

    async def add(self, revision: AgentRuntimeConfigRevision) -> None:
        self.session.add(_agent_runtime_config_revision_to_model(revision))

    async def get(
        self,
        tenant_id: str,
        asset_id: str,
        agent_id: str,
        config_revision: str,
    ) -> AgentRuntimeConfigRevision | None:
        model = await self.session.get(
            AgentRuntimeConfigRevisionModel,
            (tenant_id, asset_id, agent_id, config_revision),
        )
        return (
            _agent_runtime_config_revision_from_model(model)
            if model is not None
            else None
        )

    async def has_any_for_agent(
        self,
        tenant_id: str,
        asset_id: str,
        agent_id: str,
    ) -> bool:
        result = await self.session.scalars(
            select(AgentRuntimeConfigRevisionModel)
            .where(
                AgentRuntimeConfigRevisionModel.tenant_id == tenant_id,
                AgentRuntimeConfigRevisionModel.asset_id == asset_id,
                AgentRuntimeConfigRevisionModel.agent_id == agent_id,
            )
            .limit(1)
        )
        return result.first() is not None


@dataclass
class PostgresSourceConfigRevisionRepository:
    session: AsyncSession

    async def add(self, revision: SourceConfigRevision) -> None:
        self.session.add(_source_config_revision_to_model(revision))

    async def get(
        self,
        tenant_id: str,
        asset_id: str,
        agent_id: str,
        source_id: str,
        source_config_revision: str,
    ) -> SourceConfigRevision | None:
        model = await self.session.get(
            SourceConfigRevisionModel,
            (tenant_id, asset_id, agent_id, source_id, source_config_revision),
        )
        return (
            _source_config_revision_from_model(model)
            if model is not None
            else None
        )

    async def list_for_runtime_revision(
        self,
        tenant_id: str,
        asset_id: str,
        agent_id: str,
        config_revision: str,
    ) -> list[SourceConfigRevision]:
        result = await self.session.scalars(
            select(SourceConfigRevisionModel)
            .where(
                SourceConfigRevisionModel.tenant_id == tenant_id,
                SourceConfigRevisionModel.asset_id == asset_id,
                SourceConfigRevisionModel.agent_id == agent_id,
                SourceConfigRevisionModel.config_revision == config_revision,
            )
            .order_by(SourceConfigRevisionModel.source_id)
        )
        return [_source_config_revision_from_model(model) for model in result]

    async def has_any_for_source(
        self,
        tenant_id: str,
        asset_id: str,
        agent_id: str,
        source_id: str,
    ) -> bool:
        result = await self.session.scalars(
            select(SourceConfigRevisionModel)
            .where(
                SourceConfigRevisionModel.tenant_id == tenant_id,
                SourceConfigRevisionModel.asset_id == asset_id,
                SourceConfigRevisionModel.agent_id == agent_id,
                SourceConfigRevisionModel.source_id == source_id,
            )
            .limit(1)
        )
        return result.first() is not None


@dataclass
class PostgresConfigOutboxRepository:
    session: AsyncSession

    async def add(self, record: ConfigOutboxRecord) -> None:
        self.session.add(_config_outbox_to_model(record))

    async def get_by_idempotency_key(
        self,
        idempotency_key: str,
    ) -> ConfigOutboxRecord | None:
        result = await self.session.scalars(
            select(ConfigOutboxModel).where(
                ConfigOutboxModel.idempotency_key == idempotency_key
            )
        )
        model = result.first()
        return _config_outbox_from_model(model) if model is not None else None

    async def list_for_config_revision(
        self,
        tenant_id: str,
        asset_id: str,
        agent_id: str,
        config_revision: str,
    ) -> list[ConfigOutboxRecord]:
        result = await self.session.scalars(
            select(ConfigOutboxModel)
            .where(
                ConfigOutboxModel.tenant_id == tenant_id,
                ConfigOutboxModel.asset_id == asset_id,
                ConfigOutboxModel.agent_id == agent_id,
                ConfigOutboxModel.config_revision == config_revision,
            )
            .order_by(ConfigOutboxModel.config_scope)
        )
        return [_config_outbox_from_model(model) for model in result]

    async def has_any_for_agent(
        self,
        tenant_id: str,
        asset_id: str,
        agent_id: str,
    ) -> bool:
        result = await self.session.scalars(
            select(ConfigOutboxModel)
            .where(
                ConfigOutboxModel.tenant_id == tenant_id,
                ConfigOutboxModel.asset_id == asset_id,
                ConfigOutboxModel.agent_id == agent_id,
            )
            .limit(1)
        )
        return result.first() is not None

    async def has_any_for_source(
        self,
        tenant_id: str,
        asset_id: str,
        agent_id: str,
        source_id: str,
    ) -> bool:
        result = await self.session.scalars(
            select(ConfigOutboxModel)
            .where(
                ConfigOutboxModel.tenant_id == tenant_id,
                ConfigOutboxModel.asset_id == asset_id,
                ConfigOutboxModel.agent_id == agent_id,
                ConfigOutboxModel.source_id == source_id,
            )
            .limit(1)
        )
        return result.first() is not None

    async def reserve_available(
        self,
        *,
        limit: int,
        now: datetime,
        lease_duration: timedelta,
    ) -> list[ConfigOutboxRecord]:
        candidates_result = await self.session.scalars(
            select(ConfigOutboxModel)
            .where(
                ConfigOutboxModel.status.in_(
                    [
                        ConfigOutboxStatus.PENDING.value,
                        ConfigOutboxStatus.RETRY.value,
                    ]
                ),
                ConfigOutboxModel.available_at <= now,
                (
                    ConfigOutboxModel.next_attempt_at.is_(None)
                    | (ConfigOutboxModel.next_attempt_at <= now)
                ),
            )
            .order_by(ConfigOutboxModel.available_at, ConfigOutboxModel.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        candidates = list(candidates_result)
        reserved: list[ConfigOutboxRecord] = []
        for model in candidates:
            model.status = ConfigOutboxStatus.INFLIGHT.value
            model.lease_expires_at = now + lease_duration
            model.updated_at = now
            reserved.append(_config_outbox_from_model(model))
        await self.session.flush()
        return reserved

    async def mark_published(
        self,
        outbox_id: UUID,
        *,
        now: datetime,
    ) -> ConfigOutboxRecord | None:
        model = await self.session.get(ConfigOutboxModel, outbox_id)
        if model is None:
            return None
        model.status = ConfigOutboxStatus.PUBLISHED.value
        model.lease_expires_at = None
        model.published_at = now
        model.updated_at = now
        await self.session.flush()
        return _config_outbox_from_model(model)

    async def mark_retry(
        self,
        outbox_id: UUID,
        *,
        now: datetime,
        error: str,
        next_attempt_at: datetime,
    ) -> ConfigOutboxRecord | None:
        model = await self.session.get(ConfigOutboxModel, outbox_id)
        if model is None:
            return None
        model.status = ConfigOutboxStatus.RETRY.value
        model.lease_expires_at = None
        model.attempt_count += 1
        model.next_attempt_at = next_attempt_at
        model.last_error = error
        model.updated_at = now
        await self.session.flush()
        return _config_outbox_from_model(model)

    async def mark_dead_letter(
        self,
        outbox_id: UUID,
        *,
        now: datetime,
        error: str,
    ) -> ConfigOutboxRecord | None:
        model = await self.session.get(ConfigOutboxModel, outbox_id)
        if model is None:
            return None
        model.status = ConfigOutboxStatus.DEAD_LETTER.value
        model.lease_expires_at = None
        model.attempt_count += 1
        model.last_error = error
        model.updated_at = now
        await self.session.flush()
        return _config_outbox_from_model(model)

    async def release_expired_leases(
        self,
        *,
        now: datetime,
    ) -> int:
        result = await self.session.execute(
            update(ConfigOutboxModel)
            .where(
                ConfigOutboxModel.status == ConfigOutboxStatus.INFLIGHT.value,
                ConfigOutboxModel.lease_expires_at.is_not(None),
                ConfigOutboxModel.lease_expires_at <= now,
            )
            .values(
                status=ConfigOutboxStatus.RETRY.value,
                lease_expires_at=None,
                next_attempt_at=now,
                updated_at=now,
            )
        )
        await self.session.flush()
        return result.rowcount or 0


@dataclass
class PostgresUnitOfWork:
    session_factory: async_sessionmaker[AsyncSession]
    tenants: PostgresTenantRepository = field(init=False)
    assets: PostgresAssetRepository = field(init=False)
    agents: PostgresAgentRepository = field(init=False)
    sources: PostgresSourceRepository = field(init=False)
    points: PostgresPointRepository = field(init=False)
    agent_runtime_config_revisions: PostgresAgentRuntimeConfigRevisionRepository = field(
        init=False
    )
    source_config_revisions: PostgresSourceConfigRevisionRepository = field(
        init=False
    )
    config_outbox: PostgresConfigOutboxRepository = field(init=False)
    _session: AsyncSession = field(init=False)
    _committed: bool = field(default=False, init=False)

    async def __aenter__(self) -> PostgresUnitOfWork:
        self._session = self.session_factory()
        self.tenants = PostgresTenantRepository(self._session)
        self.assets = PostgresAssetRepository(self._session)
        self.agents = PostgresAgentRepository(self._session)
        self.sources = PostgresSourceRepository(self._session)
        self.points = PostgresPointRepository(self._session)
        self.agent_runtime_config_revisions = PostgresAgentRuntimeConfigRevisionRepository(
            self._session
        )
        self.source_config_revisions = PostgresSourceConfigRevisionRepository(
            self._session
        )
        self.config_outbox = PostgresConfigOutboxRepository(self._session)
        self._committed = False
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if exc_type is not None or not self._committed:
            await self._session.rollback()
        await self._session.close()

    async def commit(self) -> None:
        await self._session.commit()
        self._committed = True


@dataclass(frozen=True)
class PostgresUnitOfWorkFactory:
    session_manager: PostgresSessionManager

    @classmethod
    def from_url(cls, database_url: str) -> PostgresUnitOfWorkFactory:
        return cls(session_manager=PostgresSessionManager.from_url(database_url))

    def __call__(self) -> PostgresUnitOfWork:
        return PostgresUnitOfWork(self.session_manager.session_factory)

    async def dispose(self) -> None:
        await self.session_manager.dispose()
