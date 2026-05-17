from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from types import TracebackType
from uuid import UUID, uuid4

from sqlalchemy import delete, select, update
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
        id=uuid4(),
        code=tenant.tenant_code,
        name=tenant.name,
        status=tenant.status.value,
        created_at=tenant.created_at,
        updated_at=tenant.updated_at,
    )


def _tenant_from_model(model: TenantModel) -> Tenant:
    return Tenant(
        tenant_code=model.code,
        name=model.name,
        status=TenantStatus(model.status),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _asset_from_model(
    model: AssetModel,
    *,
    tenant_code: str,
) -> Asset:
    return Asset(
        tenant_code=tenant_code,
        asset_code=model.code,
        name=model.name,
        description=model.description,
        status=AssetStatus(model.status),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _agent_from_model(
    model: AgentModel,
    *,
    tenant_code: str,
    asset_code: str,
) -> Agent:
    return Agent(
        tenant_code=tenant_code,
        asset_code=asset_code,
        agent_code=model.code,
        name=model.name,
        status=AgentStatus(model.status),
        bootstrap_hint_json=dict(model.bootstrap_hint_json),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _source_from_model(
    model: SourceModel,
    *,
    tenant_code: str,
    asset_code: str,
    agent_code: str,
) -> Source:
    return Source(
        tenant_code=tenant_code,
        asset_code=asset_code,
        agent_code=agent_code,
        source_code=model.code,
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


def _point_from_model(
    model: PointModel,
    *,
    tenant_code: str,
    asset_code: str,
    agent_code: str,
    source_code: str,
) -> Point:
    return Point(
        tenant_code=tenant_code,
        asset_code=asset_code,
        agent_code=agent_code,
        source_code=source_code,
        point_code=model.code,
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


def _agent_runtime_config_revision_from_model(
    model: AgentRuntimeConfigRevisionModel,
) -> AgentRuntimeConfigRevision:
    return AgentRuntimeConfigRevision(
        tenant_code=model.tenant_code,
        asset_code=model.asset_code,
        agent_code=model.agent_code,
        config_revision=model.config_revision,
        status=ConfigRevisionStatus(model.status),
        issued_at=model.issued_at,
        agent_runtime_payload_json=dict(model.agent_runtime_payload_json),
        created_at=model.created_at,
    )


def _source_config_revision_from_model(
    model: SourceConfigRevisionModel,
) -> SourceConfigRevision:
    return SourceConfigRevision(
        tenant_code=model.tenant_code,
        asset_code=model.asset_code,
        agent_code=model.agent_code,
        source_code=model.source_code,
        source_config_revision=model.source_config_revision,
        config_revision=model.config_revision,
        status=ConfigRevisionStatus(model.status),
        issued_at=model.issued_at,
        source_payload_json=dict(model.source_payload_json),
        created_at=model.created_at,
    )


def _config_outbox_from_model(model: ConfigOutboxModel) -> ConfigOutboxRecord:
    return ConfigOutboxRecord(
        tenant_code=model.tenant_code,
        outbox_id=model.outbox_id,
        idempotency_key=model.idempotency_key,
        asset_code=model.asset_code,
        agent_code=model.agent_code,
        config_revision=model.config_revision,
        config_scope=model.config_scope,
        source_code=model.source_code,
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


def _rowcount(value: int | None) -> int:
    return int(value or 0)


async def _tenant_model_by_code(
    session: AsyncSession,
    tenant_code: str,
) -> TenantModel | None:
    result = await session.scalars(
        select(TenantModel).where(TenantModel.code == tenant_code)
    )
    return result.first()


async def _asset_context(
    session: AsyncSession,
    tenant_code: str,
    asset_code: str,
) -> tuple[TenantModel, AssetModel] | None:
    result = await session.execute(
        select(TenantModel, AssetModel)
        .join(AssetModel, AssetModel.tenant_id == TenantModel.id)
        .where(
            TenantModel.code == tenant_code,
            AssetModel.code == asset_code,
        )
    )
    return result.first()


async def _agent_context(
    session: AsyncSession,
    tenant_code: str,
    asset_code: str,
    agent_code: str,
) -> tuple[TenantModel, AssetModel, AgentModel] | None:
    result = await session.execute(
        select(TenantModel, AssetModel, AgentModel)
        .join(AssetModel, AssetModel.tenant_id == TenantModel.id)
        .join(AgentModel, AgentModel.asset_id == AssetModel.id)
        .where(
            TenantModel.code == tenant_code,
            AssetModel.code == asset_code,
            AgentModel.code == agent_code,
        )
    )
    return result.first()


async def _source_context(
    session: AsyncSession,
    tenant_code: str,
    asset_code: str,
    agent_code: str,
    source_code: str,
) -> tuple[TenantModel, AssetModel, AgentModel, SourceModel] | None:
    result = await session.execute(
        select(TenantModel, AssetModel, AgentModel, SourceModel)
        .join(AssetModel, AssetModel.tenant_id == TenantModel.id)
        .join(AgentModel, AgentModel.asset_id == AssetModel.id)
        .join(SourceModel, SourceModel.agent_id == AgentModel.id)
        .where(
            TenantModel.code == tenant_code,
            AssetModel.code == asset_code,
            AgentModel.code == agent_code,
            SourceModel.code == source_code,
        )
    )
    return result.first()


async def _point_context_by_code(
    session: AsyncSession,
    tenant_code: str,
    point_code: str,
) -> tuple[TenantModel, AssetModel, AgentModel, SourceModel, PointModel] | None:
    result = await session.execute(
        select(TenantModel, AssetModel, AgentModel, SourceModel, PointModel)
        .join(AssetModel, AssetModel.tenant_id == TenantModel.id)
        .join(AgentModel, AgentModel.asset_id == AssetModel.id)
        .join(SourceModel, SourceModel.agent_id == AgentModel.id)
        .join(PointModel, PointModel.source_id == SourceModel.id)
        .where(
            TenantModel.code == tenant_code,
            PointModel.code == point_code,
        )
    )
    return result.first()


async def _point_context_by_source_scope(
    session: AsyncSession,
    tenant_code: str,
    asset_code: str,
    agent_code: str,
    source_code: str,
    *,
    point_key: str | None = None,
    point_ref: str | None = None,
) -> tuple[TenantModel, AssetModel, AgentModel, SourceModel, PointModel] | None:
    criteria = [
        TenantModel.code == tenant_code,
        AssetModel.code == asset_code,
        AgentModel.code == agent_code,
        SourceModel.code == source_code,
    ]
    if point_key is not None:
        criteria.append(PointModel.point_key == point_key)
    if point_ref is not None:
        criteria.append(PointModel.point_ref == point_ref)
    result = await session.execute(
        select(TenantModel, AssetModel, AgentModel, SourceModel, PointModel)
        .join(AssetModel, AssetModel.tenant_id == TenantModel.id)
        .join(AgentModel, AgentModel.asset_id == AssetModel.id)
        .join(SourceModel, SourceModel.agent_id == AgentModel.id)
        .join(PointModel, PointModel.source_id == SourceModel.id)
        .where(*criteria)
    )
    return result.first()


async def _agent_runtime_revision_model_by_codes(
    session: AsyncSession,
    tenant_code: str,
    asset_code: str,
    agent_code: str,
    config_revision: str,
) -> AgentRuntimeConfigRevisionModel | None:
    result = await session.scalars(
        select(AgentRuntimeConfigRevisionModel).where(
            AgentRuntimeConfigRevisionModel.tenant_code == tenant_code,
            AgentRuntimeConfigRevisionModel.asset_code == asset_code,
            AgentRuntimeConfigRevisionModel.agent_code == agent_code,
            AgentRuntimeConfigRevisionModel.config_revision == config_revision,
        )
    )
    return result.first()


@dataclass
class PostgresTenantRepository:
    session: AsyncSession

    async def add(self, tenant: Tenant) -> None:
        self.session.add(_tenant_to_model(tenant))

    async def get(self, tenant_code: str) -> Tenant | None:
        model = await _tenant_model_by_code(self.session, tenant_code)
        return _tenant_from_model(model) if model is not None else None

    async def update(self, tenant: Tenant) -> None:
        model = await _tenant_model_by_code(self.session, tenant.tenant_code)
        if model is not None:
            model.name = tenant.name
            model.status = tenant.status.value
            model.updated_at = tenant.updated_at
            await self.session.flush()

    async def delete(self, tenant_code: str) -> None:
        model = await _tenant_model_by_code(self.session, tenant_code)
        if model is not None:
            await self.session.delete(model)
            await self.session.flush()

    async def list(self) -> list[Tenant]:
        result = await self.session.scalars(
            select(TenantModel).order_by(TenantModel.code)
        )
        return [_tenant_from_model(model) for model in result]


@dataclass
class PostgresAssetRepository:
    session: AsyncSession

    async def add(self, asset: Asset) -> None:
        tenant_model = await _tenant_model_by_code(self.session, asset.tenant_code)
        if tenant_model is None:
            return
        self.session.add(
            AssetModel(
                id=uuid4(),
                tenant_id=tenant_model.id,
                code=asset.asset_code,
                name=asset.name,
                description=asset.description,
                status=asset.status.value,
                created_at=asset.created_at,
                updated_at=asset.updated_at,
            )
        )

    async def get(self, tenant_code: str, asset_code: str) -> Asset | None:
        context = await _asset_context(self.session, tenant_code, asset_code)
        if context is None:
            return None
        _, model = context
        return _asset_from_model(model, tenant_code=tenant_code)

    async def update(self, asset: Asset) -> None:
        context = await _asset_context(
            self.session,
            asset.tenant_code,
            asset.asset_code,
        )
        if context is not None:
            _, model = context
            model.name = asset.name
            model.description = asset.description
            model.status = asset.status.value
            model.updated_at = asset.updated_at
            await self.session.flush()

    async def delete(self, tenant_code: str, asset_code: str) -> None:
        context = await _asset_context(self.session, tenant_code, asset_code)
        if context is not None:
            _, model = context
            await self.session.delete(model)
            await self.session.flush()

    async def list_for_tenant(self, tenant_code: str) -> list[Asset]:
        tenant_model = await _tenant_model_by_code(self.session, tenant_code)
        if tenant_model is None:
            return []
        result = await self.session.scalars(
            select(AssetModel)
            .where(AssetModel.tenant_id == tenant_model.id)
            .order_by(AssetModel.code)
        )
        return [
            _asset_from_model(model, tenant_code=tenant_code)
            for model in result
        ]


@dataclass
class PostgresAgentRepository:
    session: AsyncSession

    async def add(self, agent: Agent) -> None:
        context = await _asset_context(
            self.session,
            agent.tenant_code,
            agent.asset_code,
        )
        if context is None:
            return
        tenant_model, asset_model = context
        self.session.add(
            AgentModel(
                id=uuid4(),
                tenant_id=tenant_model.id,
                asset_id=asset_model.id,
                code=agent.agent_code,
                name=agent.name,
                status=agent.status.value,
                bootstrap_hint_json=dict(agent.bootstrap_hint_json),
                created_at=agent.created_at,
                updated_at=agent.updated_at,
            )
        )

    async def get(
        self,
        tenant_code: str,
        asset_code: str,
        agent_code: str,
    ) -> Agent | None:
        context = await _agent_context(
            self.session,
            tenant_code,
            asset_code,
            agent_code,
        )
        if context is None:
            return None
        _, _, model = context
        return _agent_from_model(
            model,
            tenant_code=tenant_code,
            asset_code=asset_code,
        )

    async def update(self, agent: Agent) -> None:
        context = await _agent_context(
            self.session,
            agent.tenant_code,
            agent.asset_code,
            agent.agent_code,
        )
        if context is not None:
            _, _, model = context
            model.name = agent.name
            model.status = agent.status.value
            model.bootstrap_hint_json = dict(agent.bootstrap_hint_json)
            model.updated_at = agent.updated_at
            await self.session.flush()

    async def delete(
        self,
        tenant_code: str,
        asset_code: str,
        agent_code: str,
    ) -> None:
        context = await _agent_context(
            self.session,
            tenant_code,
            asset_code,
            agent_code,
        )
        if context is not None:
            _, _, model = context
            await self.session.delete(model)
            await self.session.flush()

    async def list_for_asset(
        self,
        tenant_code: str,
        asset_code: str,
    ) -> list[Agent]:
        context = await _asset_context(self.session, tenant_code, asset_code)
        if context is None:
            return []
        _, asset_model = context
        result = await self.session.scalars(
            select(AgentModel)
            .where(AgentModel.asset_id == asset_model.id)
            .order_by(AgentModel.code)
        )
        return [
            _agent_from_model(
                model,
                tenant_code=tenant_code,
                asset_code=asset_code,
            )
            for model in result
        ]


@dataclass
class PostgresSourceRepository:
    session: AsyncSession

    async def add(self, source: Source) -> None:
        context = await _agent_context(
            self.session,
            source.tenant_code,
            source.asset_code,
            source.agent_code,
        )
        if context is None:
            return
        tenant_model, _, agent_model = context
        self.session.add(
            SourceModel(
                id=uuid4(),
                tenant_id=tenant_model.id,
                agent_id=agent_model.id,
                code=source.source_code,
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
        )

    async def get(
        self,
        tenant_code: str,
        asset_code: str,
        agent_code: str,
        source_code: str,
    ) -> Source | None:
        context = await _source_context(
            self.session,
            tenant_code,
            asset_code,
            agent_code,
            source_code,
        )
        if context is None:
            return None
        _, _, _, model = context
        return _source_from_model(
            model,
            tenant_code=tenant_code,
            asset_code=asset_code,
            agent_code=agent_code,
        )

    async def update(self, source: Source) -> None:
        context = await _source_context(
            self.session,
            source.tenant_code,
            source.asset_code,
            source.agent_code,
            source.source_code,
        )
        if context is not None:
            _, _, _, model = context
            model.source_type = source.source_type
            model.enabled = source.enabled
            model.name = source.name
            model.description = source.description
            model.connection_json = dict(source.connection_json)
            model.acquisition_defaults_json = dict(source.acquisition_defaults_json)
            model.publish_defaults_json = dict(source.publish_defaults_json)
            model.updated_at = source.updated_at
            await self.session.flush()

    async def delete(
        self,
        tenant_code: str,
        asset_code: str,
        agent_code: str,
        source_code: str,
    ) -> None:
        context = await _source_context(
            self.session,
            tenant_code,
            asset_code,
            agent_code,
            source_code,
        )
        if context is not None:
            _, _, _, model = context
            await self.session.delete(model)
            await self.session.flush()

    async def delete_for_agent(
        self,
        tenant_code: str,
        asset_code: str,
        agent_code: str,
    ) -> int:
        context = await _agent_context(
            self.session,
            tenant_code,
            asset_code,
            agent_code,
        )
        if context is None:
            return 0
        _, _, agent_model = context
        result = await self.session.execute(
            delete(SourceModel).where(SourceModel.agent_id == agent_model.id)
        )
        await self.session.flush()
        return _rowcount(result.rowcount)

    async def list_for_agent(
        self,
        tenant_code: str,
        asset_code: str,
        agent_code: str,
    ) -> list[Source]:
        context = await _agent_context(
            self.session,
            tenant_code,
            asset_code,
            agent_code,
        )
        if context is None:
            return []
        _, _, agent_model = context
        result = await self.session.scalars(
            select(SourceModel)
            .where(SourceModel.agent_id == agent_model.id)
            .order_by(SourceModel.code)
        )
        return [
            _source_from_model(
                model,
                tenant_code=tenant_code,
                asset_code=asset_code,
                agent_code=agent_code,
            )
            for model in result
        ]


@dataclass
class PostgresPointRepository:
    session: AsyncSession

    async def add(self, point: Point) -> None:
        context = await _source_context(
            self.session,
            point.tenant_code,
            point.asset_code,
            point.agent_code,
            point.source_code,
        )
        if context is None:
            return
        tenant_model, _, _, source_model = context
        self.session.add(
            PointModel(
                id=uuid4(),
                tenant_id=tenant_model.id,
                source_id=source_model.id,
                code=point.point_code,
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
        )

    async def get_by_id(self, tenant_code: str, point_code: str) -> Point | None:
        context = await _point_context_by_code(self.session, tenant_code, point_code)
        if context is None:
            return None
        _, asset_model, agent_model, source_model, model = context
        return _point_from_model(
            model,
            tenant_code=tenant_code,
            asset_code=asset_model.code,
            agent_code=agent_model.code,
            source_code=source_model.code,
        )

    async def update(self, point: Point) -> None:
        context = await _point_context_by_code(
            self.session,
            point.tenant_code,
            point.point_code,
        )
        if context is not None:
            _, _, _, _, model = context
            model.point_key = point.point_key
            model.point_ref = point.point_ref
            model.name = point.name
            model.description = point.description
            model.value_type = point.value_type.value
            model.value_model = point.value_model
            model.signal_type = point.signal_type.value
            model.unit = point.unit
            model.enabled = point.enabled
            model.acquisition_json = dict(point.acquisition_json)
            model.publish_json = dict(point.publish_json)
            model.tags_json = dict(point.tags_json)
            model.updated_at = point.updated_at
            await self.session.flush()

    async def delete(self, tenant_code: str, point_code: str) -> None:
        context = await _point_context_by_code(self.session, tenant_code, point_code)
        if context is not None:
            _, _, _, _, model = context
            await self.session.delete(model)
            await self.session.flush()

    async def delete_for_agent(
        self,
        tenant_code: str,
        asset_code: str,
        agent_code: str,
    ) -> int:
        context = await _agent_context(
            self.session,
            tenant_code,
            asset_code,
            agent_code,
        )
        if context is None:
            return 0
        _, _, agent_model = context
        source_ids = select(SourceModel.id).where(SourceModel.agent_id == agent_model.id)
        result = await self.session.execute(
            delete(PointModel).where(PointModel.source_id.in_(source_ids))
        )
        await self.session.flush()
        return _rowcount(result.rowcount)

    async def get_by_key(
        self,
        tenant_code: str,
        asset_code: str,
        agent_code: str,
        source_code: str,
        point_key: str,
    ) -> Point | None:
        context = await _point_context_by_source_scope(
            self.session,
            tenant_code,
            asset_code,
            agent_code,
            source_code,
            point_key=point_key,
        )
        if context is None:
            return None
        _, _, _, _, model = context
        return _point_from_model(
            model,
            tenant_code=tenant_code,
            asset_code=asset_code,
            agent_code=agent_code,
            source_code=source_code,
        )

    async def get_by_ref(
        self,
        tenant_code: str,
        asset_code: str,
        agent_code: str,
        source_code: str,
        point_ref: str,
    ) -> Point | None:
        context = await _point_context_by_source_scope(
            self.session,
            tenant_code,
            asset_code,
            agent_code,
            source_code,
            point_ref=point_ref,
        )
        if context is None:
            return None
        _, _, _, _, model = context
        return _point_from_model(
            model,
            tenant_code=tenant_code,
            asset_code=asset_code,
            agent_code=agent_code,
            source_code=source_code,
        )

    async def list_for_source(
        self,
        tenant_code: str,
        asset_code: str,
        agent_code: str,
        source_code: str,
    ) -> list[Point]:
        context = await _source_context(
            self.session,
            tenant_code,
            asset_code,
            agent_code,
            source_code,
        )
        if context is None:
            return []
        _, _, _, source_model = context
        result = await self.session.scalars(
            select(PointModel)
            .where(PointModel.source_id == source_model.id)
            .order_by(PointModel.point_key)
        )
        return [
            _point_from_model(
                model,
                tenant_code=tenant_code,
                asset_code=asset_code,
                agent_code=agent_code,
                source_code=source_code,
            )
            for model in result
        ]


@dataclass
class PostgresAgentRuntimeConfigRevisionRepository:
    session: AsyncSession

    async def add(self, revision: AgentRuntimeConfigRevision) -> None:
        context = await _agent_context(
            self.session,
            revision.tenant_code,
            revision.asset_code,
            revision.agent_code,
        )
        if context is None:
            return
        tenant_model, asset_model, agent_model = context
        self.session.add(
            AgentRuntimeConfigRevisionModel(
                id=uuid4(),
                tenant_id=tenant_model.id,
                asset_id=asset_model.id,
                agent_id=agent_model.id,
                tenant_code=revision.tenant_code,
                asset_code=revision.asset_code,
                agent_code=revision.agent_code,
                config_revision=revision.config_revision,
                status=revision.status.value,
                issued_at=revision.issued_at,
                agent_runtime_payload_json=dict(
                    revision.agent_runtime_payload_json
                ),
                created_at=revision.created_at,
            )
        )

    async def get(
        self,
        tenant_code: str,
        asset_code: str,
        agent_code: str,
        config_revision: str,
    ) -> AgentRuntimeConfigRevision | None:
        model = await _agent_runtime_revision_model_by_codes(
            self.session,
            tenant_code,
            asset_code,
            agent_code,
            config_revision,
        )
        return (
            _agent_runtime_config_revision_from_model(model)
            if model is not None
            else None
        )

    async def has_any_for_agent(
        self,
        tenant_code: str,
        asset_code: str,
        agent_code: str,
    ) -> bool:
        result = await self.session.scalars(
            select(AgentRuntimeConfigRevisionModel)
            .where(
                AgentRuntimeConfigRevisionModel.tenant_code == tenant_code,
                AgentRuntimeConfigRevisionModel.asset_code == asset_code,
                AgentRuntimeConfigRevisionModel.agent_code == agent_code,
            )
            .limit(1)
        )
        return result.first() is not None

    async def delete_for_agent(
        self,
        tenant_code: str,
        asset_code: str,
        agent_code: str,
    ) -> int:
        result = await self.session.execute(
            delete(AgentRuntimeConfigRevisionModel).where(
                AgentRuntimeConfigRevisionModel.tenant_code == tenant_code,
                AgentRuntimeConfigRevisionModel.asset_code == asset_code,
                AgentRuntimeConfigRevisionModel.agent_code == agent_code,
            )
        )
        await self.session.flush()
        return _rowcount(result.rowcount)


@dataclass
class PostgresSourceConfigRevisionRepository:
    session: AsyncSession

    async def add(self, revision: SourceConfigRevision) -> None:
        context = await _source_context(
            self.session,
            revision.tenant_code,
            revision.asset_code,
            revision.agent_code,
            revision.source_code,
        )
        runtime_revision = await _agent_runtime_revision_model_by_codes(
            self.session,
            revision.tenant_code,
            revision.asset_code,
            revision.agent_code,
            revision.config_revision,
        )
        if context is None or runtime_revision is None:
            return
        tenant_model, asset_model, agent_model, source_model = context
        self.session.add(
            SourceConfigRevisionModel(
                id=uuid4(),
                tenant_id=tenant_model.id,
                asset_id=asset_model.id,
                agent_id=agent_model.id,
                source_id=source_model.id,
                agent_runtime_config_revision_id=runtime_revision.id,
                tenant_code=revision.tenant_code,
                asset_code=revision.asset_code,
                agent_code=revision.agent_code,
                source_code=revision.source_code,
                source_config_revision=revision.source_config_revision,
                config_revision=revision.config_revision,
                status=revision.status.value,
                issued_at=revision.issued_at,
                source_payload_json=dict(revision.source_payload_json),
                created_at=revision.created_at,
            )
        )

    async def get(
        self,
        tenant_code: str,
        asset_code: str,
        agent_code: str,
        source_code: str,
        source_config_revision: str,
    ) -> SourceConfigRevision | None:
        result = await self.session.scalars(
            select(SourceConfigRevisionModel).where(
                SourceConfigRevisionModel.tenant_code == tenant_code,
                SourceConfigRevisionModel.asset_code == asset_code,
                SourceConfigRevisionModel.agent_code == agent_code,
                SourceConfigRevisionModel.source_code == source_code,
                SourceConfigRevisionModel.source_config_revision
                == source_config_revision,
            )
        )
        model = result.first()
        return (
            _source_config_revision_from_model(model)
            if model is not None
            else None
        )

    async def list_for_runtime_revision(
        self,
        tenant_code: str,
        asset_code: str,
        agent_code: str,
        config_revision: str,
    ) -> list[SourceConfigRevision]:
        result = await self.session.scalars(
            select(SourceConfigRevisionModel)
            .where(
                SourceConfigRevisionModel.tenant_code == tenant_code,
                SourceConfigRevisionModel.asset_code == asset_code,
                SourceConfigRevisionModel.agent_code == agent_code,
                SourceConfigRevisionModel.config_revision == config_revision,
            )
            .order_by(SourceConfigRevisionModel.source_code)
        )
        return [_source_config_revision_from_model(model) for model in result]

    async def has_any_for_source(
        self,
        tenant_code: str,
        asset_code: str,
        agent_code: str,
        source_code: str,
    ) -> bool:
        result = await self.session.scalars(
            select(SourceConfigRevisionModel)
            .where(
                SourceConfigRevisionModel.tenant_code == tenant_code,
                SourceConfigRevisionModel.asset_code == asset_code,
                SourceConfigRevisionModel.agent_code == agent_code,
                SourceConfigRevisionModel.source_code == source_code,
            )
            .limit(1)
        )
        return result.first() is not None

    async def delete_for_agent(
        self,
        tenant_code: str,
        asset_code: str,
        agent_code: str,
    ) -> int:
        result = await self.session.execute(
            delete(SourceConfigRevisionModel).where(
                SourceConfigRevisionModel.tenant_code == tenant_code,
                SourceConfigRevisionModel.asset_code == asset_code,
                SourceConfigRevisionModel.agent_code == agent_code,
            )
        )
        await self.session.flush()
        return _rowcount(result.rowcount)


@dataclass
class PostgresConfigOutboxRepository:
    session: AsyncSession

    async def add(self, record: ConfigOutboxRecord) -> None:
        context = await _agent_context(
            self.session,
            record.tenant_code,
            record.asset_code,
            record.agent_code,
        )
        if context is None:
            return
        tenant_model, asset_model, agent_model = context
        source_model = None
        if record.source_code is not None:
            source_context = await _source_context(
                self.session,
                record.tenant_code,
                record.asset_code,
                record.agent_code,
                record.source_code,
            )
            if source_context is None:
                return
            _, _, _, source_model = source_context
        self.session.add(
            ConfigOutboxModel(
                outbox_id=record.outbox_id,
                tenant_id=tenant_model.id,
                asset_id=asset_model.id,
                agent_id=agent_model.id,
                source_id=source_model.id if source_model is not None else None,
                idempotency_key=record.idempotency_key,
                tenant_code=record.tenant_code,
                asset_code=record.asset_code,
                agent_code=record.agent_code,
                source_code=record.source_code,
                config_revision=record.config_revision,
                config_scope=record.config_scope,
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
        )

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
        tenant_code: str,
        asset_code: str,
        agent_code: str,
        config_revision: str,
    ) -> list[ConfigOutboxRecord]:
        result = await self.session.scalars(
            select(ConfigOutboxModel)
            .where(
                ConfigOutboxModel.tenant_code == tenant_code,
                ConfigOutboxModel.asset_code == asset_code,
                ConfigOutboxModel.agent_code == agent_code,
                ConfigOutboxModel.config_revision == config_revision,
            )
            .order_by(ConfigOutboxModel.config_scope)
        )
        return [_config_outbox_from_model(model) for model in result]

    async def has_any_for_agent(
        self,
        tenant_code: str,
        asset_code: str,
        agent_code: str,
    ) -> bool:
        result = await self.session.scalars(
            select(ConfigOutboxModel)
            .where(
                ConfigOutboxModel.tenant_code == tenant_code,
                ConfigOutboxModel.asset_code == asset_code,
                ConfigOutboxModel.agent_code == agent_code,
            )
            .limit(1)
        )
        return result.first() is not None

    async def has_any_for_source(
        self,
        tenant_code: str,
        asset_code: str,
        agent_code: str,
        source_code: str,
    ) -> bool:
        result = await self.session.scalars(
            select(ConfigOutboxModel)
            .where(
                ConfigOutboxModel.tenant_code == tenant_code,
                ConfigOutboxModel.asset_code == asset_code,
                ConfigOutboxModel.agent_code == agent_code,
                ConfigOutboxModel.source_code == source_code,
            )
            .limit(1)
        )
        return result.first() is not None

    async def delete_for_agent(
        self,
        tenant_code: str,
        asset_code: str,
        agent_code: str,
    ) -> int:
        result = await self.session.execute(
            delete(ConfigOutboxModel).where(
                ConfigOutboxModel.tenant_code == tenant_code,
                ConfigOutboxModel.asset_code == asset_code,
                ConfigOutboxModel.agent_code == agent_code,
            )
        )
        await self.session.flush()
        return _rowcount(result.rowcount)

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
        return _rowcount(result.rowcount)


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
