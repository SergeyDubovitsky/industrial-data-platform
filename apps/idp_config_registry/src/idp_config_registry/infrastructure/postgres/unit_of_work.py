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


def _tenant_from_model(model: TenantModel) -> Tenant:
    return Tenant(
        tenant_id=model.tenant_id,
        name=model.name,
        status=TenantStatus(model.status),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _asset_from_row(model: AssetModel, tenant: TenantModel) -> Asset:
    return Asset(
        tenant_id=tenant.tenant_id,
        asset_id=model.asset_id,
        name=model.name,
        description=model.description,
        status=AssetStatus(model.status),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _agent_from_row(
    model: AgentModel,
    asset: AssetModel,
    tenant: TenantModel,
) -> Agent:
    return Agent(
        tenant_id=tenant.tenant_id,
        asset_id=asset.asset_id,
        agent_id=model.agent_id,
        name=model.name,
        status=AgentStatus(model.status),
        bootstrap_hint_json=dict(model.bootstrap_hint_json),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _source_from_row(
    model: SourceModel,
    agent: AgentModel,
    asset: AssetModel,
    tenant: TenantModel,
) -> Source:
    return Source(
        tenant_id=tenant.tenant_id,
        asset_id=asset.asset_id,
        agent_id=agent.agent_id,
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


def _point_from_row(
    model: PointModel,
    source: SourceModel,
    agent: AgentModel,
    asset: AssetModel,
    tenant: TenantModel,
) -> Point:
    return Point(
        tenant_id=tenant.tenant_id,
        asset_id=asset.asset_id,
        agent_id=agent.agent_id,
        source_id=source.source_id,
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


def _agent_runtime_config_revision_from_row(
    model: AgentRuntimeConfigRevisionModel,
    agent: AgentModel,
    asset: AssetModel,
    tenant: TenantModel,
) -> AgentRuntimeConfigRevision:
    return AgentRuntimeConfigRevision(
        tenant_id=tenant.tenant_id,
        asset_id=asset.asset_id,
        agent_id=agent.agent_id,
        config_revision=model.config_revision,
        status=ConfigRevisionStatus(model.status),
        issued_at=model.issued_at,
        agent_runtime_payload_json=dict(model.agent_runtime_payload_json),
        created_at=model.created_at,
    )


def _source_config_revision_from_row(
    model: SourceConfigRevisionModel,
    source: SourceModel,
    agent: AgentModel,
    asset: AssetModel,
    tenant: TenantModel,
) -> SourceConfigRevision:
    return SourceConfigRevision(
        tenant_id=tenant.tenant_id,
        asset_id=asset.asset_id,
        agent_id=agent.agent_id,
        source_id=source.source_id,
        source_config_revision=model.source_config_revision,
        config_revision=model.config_revision,
        status=ConfigRevisionStatus(model.status),
        issued_at=model.issued_at,
        source_payload_json=dict(model.source_payload_json),
        created_at=model.created_at,
    )


def _config_outbox_from_row(
    model: ConfigOutboxModel,
    tenant: TenantModel,
    asset: AssetModel,
    agent: AgentModel,
    source: SourceModel | None,
) -> ConfigOutboxRecord:
    return ConfigOutboxRecord(
        tenant_id=tenant.tenant_id,
        outbox_id=model.id,
        idempotency_key=model.idempotency_key,
        asset_id=asset.asset_id,
        agent_id=agent.agent_id,
        config_revision=model.config_revision,
        config_scope=model.config_scope,
        source_id=source.source_id if source is not None else None,
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


async def _tenant_model_by_code(
    session: AsyncSession,
    tenant_code: str,
) -> TenantModel | None:
    result = await session.scalars(
        select(TenantModel).where(TenantModel.tenant_id == tenant_code)
    )
    return result.first()


async def _asset_row_by_codes(
    session: AsyncSession,
    tenant_code: str,
    asset_code: str,
) -> tuple[AssetModel, TenantModel] | None:
    result = await session.execute(
        select(AssetModel, TenantModel)
        .join(TenantModel, AssetModel.tenant_uuid == TenantModel.id)
        .where(TenantModel.tenant_id == tenant_code, AssetModel.asset_id == asset_code)
    )
    row = result.first()
    return (row[0], row[1]) if row is not None else None


async def _agent_row_by_codes(
    session: AsyncSession,
    tenant_code: str,
    asset_code: str,
    agent_code: str,
) -> tuple[AgentModel, AssetModel, TenantModel] | None:
    result = await session.execute(
        select(AgentModel, AssetModel, TenantModel)
        .join(AssetModel, AgentModel.asset_uuid == AssetModel.id)
        .join(TenantModel, AgentModel.tenant_uuid == TenantModel.id)
        .where(
            TenantModel.tenant_id == tenant_code,
            AssetModel.asset_id == asset_code,
            AgentModel.agent_id == agent_code,
        )
    )
    row = result.first()
    return (row[0], row[1], row[2]) if row is not None else None


async def _source_row_by_codes(
    session: AsyncSession,
    tenant_code: str,
    asset_code: str,
    agent_code: str,
    source_code: str,
) -> tuple[SourceModel, AgentModel, AssetModel, TenantModel] | None:
    result = await session.execute(
        select(SourceModel, AgentModel, AssetModel, TenantModel)
        .join(AgentModel, SourceModel.agent_uuid == AgentModel.id)
        .join(AssetModel, AgentModel.asset_uuid == AssetModel.id)
        .join(TenantModel, SourceModel.tenant_uuid == TenantModel.id)
        .where(
            TenantModel.tenant_id == tenant_code,
            AssetModel.asset_id == asset_code,
            AgentModel.agent_id == agent_code,
            SourceModel.source_id == source_code,
        )
    )
    row = result.first()
    return (row[0], row[1], row[2], row[3]) if row is not None else None


async def _point_row_by_code(
    session: AsyncSession,
    tenant_code: str,
    point_code: str,
) -> tuple[PointModel, SourceModel, AgentModel, AssetModel, TenantModel] | None:
    result = await session.execute(
        select(PointModel, SourceModel, AgentModel, AssetModel, TenantModel)
        .join(SourceModel, PointModel.source_uuid == SourceModel.id)
        .join(AgentModel, SourceModel.agent_uuid == AgentModel.id)
        .join(AssetModel, AgentModel.asset_uuid == AssetModel.id)
        .join(TenantModel, PointModel.tenant_uuid == TenantModel.id)
        .where(TenantModel.tenant_id == tenant_code, PointModel.point_id == point_code)
    )
    row = result.first()
    return (row[0], row[1], row[2], row[3], row[4]) if row is not None else None


async def _point_row_by_source_and_field(
    session: AsyncSession,
    tenant_code: str,
    asset_code: str,
    agent_code: str,
    source_code: str,
    field_name: str,
    field_value: str,
) -> tuple[PointModel, SourceModel, AgentModel, AssetModel, TenantModel] | None:
    field = PointModel.point_key if field_name == "point_key" else PointModel.point_ref
    result = await session.execute(
        select(PointModel, SourceModel, AgentModel, AssetModel, TenantModel)
        .join(SourceModel, PointModel.source_uuid == SourceModel.id)
        .join(AgentModel, SourceModel.agent_uuid == AgentModel.id)
        .join(AssetModel, AgentModel.asset_uuid == AssetModel.id)
        .join(TenantModel, PointModel.tenant_uuid == TenantModel.id)
        .where(
            TenantModel.tenant_id == tenant_code,
            AssetModel.asset_id == asset_code,
            AgentModel.agent_id == agent_code,
            SourceModel.source_id == source_code,
            field == field_value,
        )
    )
    row = result.first()
    return (row[0], row[1], row[2], row[3], row[4]) if row is not None else None


async def _agent_runtime_revision_row_by_codes(
    session: AsyncSession,
    tenant_code: str,
    asset_code: str,
    agent_code: str,
    config_revision_code: str,
) -> tuple[AgentRuntimeConfigRevisionModel, AgentModel, AssetModel, TenantModel] | None:
    result = await session.execute(
        select(AgentRuntimeConfigRevisionModel, AgentModel, AssetModel, TenantModel)
        .join(AgentModel, AgentRuntimeConfigRevisionModel.agent_uuid == AgentModel.id)
        .join(AssetModel, AgentModel.asset_uuid == AssetModel.id)
        .join(TenantModel, AgentRuntimeConfigRevisionModel.tenant_uuid == TenantModel.id)
        .where(
            TenantModel.tenant_id == tenant_code,
            AssetModel.asset_id == asset_code,
            AgentModel.agent_id == agent_code,
            AgentRuntimeConfigRevisionModel.config_revision == config_revision_code,
        )
    )
    row = result.first()
    return (row[0], row[1], row[2], row[3]) if row is not None else None


async def _source_config_revision_row_by_codes(
    session: AsyncSession,
    tenant_code: str,
    asset_code: str,
    agent_code: str,
    source_code: str,
    source_config_revision_code: str,
) -> tuple[SourceConfigRevisionModel, SourceModel, AgentModel, AssetModel, TenantModel] | None:
    result = await session.execute(
        select(SourceConfigRevisionModel, SourceModel, AgentModel, AssetModel, TenantModel)
        .join(SourceModel, SourceConfigRevisionModel.source_uuid == SourceModel.id)
        .join(AgentModel, SourceModel.agent_uuid == AgentModel.id)
        .join(AssetModel, AgentModel.asset_uuid == AssetModel.id)
        .join(TenantModel, SourceConfigRevisionModel.tenant_uuid == TenantModel.id)
        .where(
            TenantModel.tenant_id == tenant_code,
            AssetModel.asset_id == asset_code,
            AgentModel.agent_id == agent_code,
            SourceModel.source_id == source_code,
            SourceConfigRevisionModel.source_config_revision == source_config_revision_code,
        )
    )
    row = result.first()
    return (row[0], row[1], row[2], row[3], row[4]) if row is not None else None


async def _config_outbox_row_by_model(
    session: AsyncSession,
    model: ConfigOutboxModel,
) -> tuple[ConfigOutboxModel, TenantModel, AssetModel, AgentModel, SourceModel | None]:
    result = await session.execute(
        select(ConfigOutboxModel, TenantModel, AssetModel, AgentModel, SourceModel)
        .join(AgentModel, ConfigOutboxModel.agent_uuid == AgentModel.id)
        .join(AssetModel, AgentModel.asset_uuid == AssetModel.id)
        .join(TenantModel, ConfigOutboxModel.tenant_uuid == TenantModel.id)
        .outerjoin(SourceModel, ConfigOutboxModel.source_uuid == SourceModel.id)
        .where(ConfigOutboxModel.id == model.id)
    )
    row = result.one()
    return row[0], row[1], row[2], row[3], row[4]


def _rowcount(value: int | None) -> int:
    return int(value or 0)


@dataclass
class PostgresTenantRepository:
    session: AsyncSession

    async def add(self, tenant: Tenant) -> None:
        self.session.add(
            TenantModel(
                id=uuid4(),
                tenant_id=tenant.tenant_id,
                name=tenant.name,
                status=tenant.status.value,
                created_at=tenant.created_at,
                updated_at=tenant.updated_at,
            )
        )

    async def get(self, tenant_id: str) -> Tenant | None:
        model = await _tenant_model_by_code(self.session, tenant_id)
        return _tenant_from_model(model) if model is not None else None

    async def update(self, tenant: Tenant) -> None:
        model = await _tenant_model_by_code(self.session, tenant.tenant_id)
        if model is None:
            return
        model.name = tenant.name
        model.status = tenant.status.value
        model.updated_at = tenant.updated_at
        await self.session.flush()

    async def delete(self, tenant_id: str) -> None:
        model = await _tenant_model_by_code(self.session, tenant_id)
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
        tenant = await _tenant_model_by_code(self.session, asset.tenant_id)
        if tenant is None:
            raise ValueError(f"Tenant {asset.tenant_id!r} does not exist")
        self.session.add(
            AssetModel(
                id=uuid4(),
                tenant_uuid=tenant.id,
                asset_id=asset.asset_id,
                name=asset.name,
                description=asset.description,
                status=asset.status.value,
                created_at=asset.created_at,
                updated_at=asset.updated_at,
            )
        )

    async def get(self, tenant_id: str, asset_id: str) -> Asset | None:
        row = await _asset_row_by_codes(self.session, tenant_id, asset_id)
        return _asset_from_row(*row) if row is not None else None

    async def update(self, asset: Asset) -> None:
        row = await _asset_row_by_codes(self.session, asset.tenant_id, asset.asset_id)
        if row is None:
            return
        model, _tenant = row
        model.name = asset.name
        model.description = asset.description
        model.status = asset.status.value
        model.updated_at = asset.updated_at
        await self.session.flush()

    async def delete(self, tenant_id: str, asset_id: str) -> None:
        row = await _asset_row_by_codes(self.session, tenant_id, asset_id)
        if row is not None:
            await self.session.delete(row[0])
            await self.session.flush()

    async def list_for_tenant(self, tenant_id: str) -> list[Asset]:
        tenant_code = tenant_id
        result = await self.session.execute(
            select(AssetModel, TenantModel)
            .join(TenantModel, AssetModel.tenant_uuid == TenantModel.id)
            .where(TenantModel.tenant_id == tenant_code)
            .order_by(AssetModel.asset_id)
        )
        return [_asset_from_row(row[0], row[1]) for row in result]


@dataclass
class PostgresAgentRepository:
    session: AsyncSession

    async def add(self, agent: Agent) -> None:
        asset_row = await _asset_row_by_codes(
            self.session,
            agent.tenant_id,
            agent.asset_id,
        )
        if asset_row is None:
            raise ValueError(
                f"Asset {agent.tenant_id!r}/{agent.asset_id!r} does not exist"
            )
        asset, tenant = asset_row
        self.session.add(
            AgentModel(
                id=uuid4(),
                tenant_uuid=tenant.id,
                asset_uuid=asset.id,
                agent_id=agent.agent_id,
                name=agent.name,
                status=agent.status.value,
                bootstrap_hint_json=dict(agent.bootstrap_hint_json),
                created_at=agent.created_at,
                updated_at=agent.updated_at,
            )
        )

    async def get(self, tenant_id: str, asset_id: str, agent_id: str) -> Agent | None:
        row = await _agent_row_by_codes(self.session, tenant_id, asset_id, agent_id)
        return _agent_from_row(*row) if row is not None else None

    async def update(self, agent: Agent) -> None:
        row = await _agent_row_by_codes(
            self.session,
            agent.tenant_id,
            agent.asset_id,
            agent.agent_id,
        )
        if row is None:
            return
        model, _asset, _tenant = row
        model.name = agent.name
        model.status = agent.status.value
        model.bootstrap_hint_json = dict(agent.bootstrap_hint_json)
        model.updated_at = agent.updated_at
        await self.session.flush()

    async def delete(self, tenant_id: str, asset_id: str, agent_id: str) -> None:
        row = await _agent_row_by_codes(self.session, tenant_id, asset_id, agent_id)
        if row is not None:
            await self.session.delete(row[0])
            await self.session.flush()

    async def list_for_asset(self, tenant_id: str, asset_id: str) -> list[Agent]:
        tenant_code = tenant_id
        asset_code = asset_id
        result = await self.session.execute(
            select(AgentModel, AssetModel, TenantModel)
            .join(AssetModel, AgentModel.asset_uuid == AssetModel.id)
            .join(TenantModel, AgentModel.tenant_uuid == TenantModel.id)
            .where(TenantModel.tenant_id == tenant_code, AssetModel.asset_id == asset_code)
            .order_by(AgentModel.agent_id)
        )
        return [_agent_from_row(row[0], row[1], row[2]) for row in result]


@dataclass
class PostgresSourceRepository:
    session: AsyncSession

    async def add(self, source: Source) -> None:
        agent_row = await _agent_row_by_codes(
            self.session,
            source.tenant_id,
            source.asset_id,
            source.agent_id,
        )
        if agent_row is None:
            raise ValueError(
                "Agent "
                f"{source.tenant_id!r}/{source.asset_id!r}/{source.agent_id!r} "
                "does not exist"
            )
        agent, _asset, tenant = agent_row
        self.session.add(
            SourceModel(
                id=uuid4(),
                tenant_uuid=tenant.id,
                agent_uuid=agent.id,
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
        )

    async def get(
        self,
        tenant_id: str,
        asset_id: str,
        agent_id: str,
        source_id: str,
    ) -> Source | None:
        row = await _source_row_by_codes(
            self.session,
            tenant_id,
            asset_id,
            agent_id,
            source_id,
        )
        return _source_from_row(*row) if row is not None else None

    async def update(self, source: Source) -> None:
        row = await _source_row_by_codes(
            self.session,
            source.tenant_id,
            source.asset_id,
            source.agent_id,
            source.source_id,
        )
        if row is None:
            return
        model, _agent, _asset, _tenant = row
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
        tenant_id: str,
        asset_id: str,
        agent_id: str,
        source_id: str,
    ) -> None:
        row = await _source_row_by_codes(
            self.session,
            tenant_id,
            asset_id,
            agent_id,
            source_id,
        )
        if row is not None:
            await self.session.delete(row[0])
            await self.session.flush()

    async def delete_for_agent(
        self,
        tenant_id: str,
        asset_id: str,
        agent_id: str,
    ) -> int:
        agent_row = await _agent_row_by_codes(self.session, tenant_id, asset_id, agent_id)
        if agent_row is None:
            return 0
        agent, _asset, _tenant = agent_row
        result = await self.session.execute(
            delete(SourceModel).where(SourceModel.agent_uuid == agent.id)
        )
        await self.session.flush()
        return _rowcount(result.rowcount)

    async def list_for_agent(
        self,
        tenant_id: str,
        asset_id: str,
        agent_id: str,
    ) -> list[Source]:
        tenant_code = tenant_id
        asset_code = asset_id
        agent_code = agent_id
        result = await self.session.execute(
            select(SourceModel, AgentModel, AssetModel, TenantModel)
            .join(AgentModel, SourceModel.agent_uuid == AgentModel.id)
            .join(AssetModel, AgentModel.asset_uuid == AssetModel.id)
            .join(TenantModel, SourceModel.tenant_uuid == TenantModel.id)
            .where(
                TenantModel.tenant_id == tenant_code,
                AssetModel.asset_id == asset_code,
                AgentModel.agent_id == agent_code,
            )
            .order_by(SourceModel.source_id)
        )
        return [_source_from_row(row[0], row[1], row[2], row[3]) for row in result]


@dataclass
class PostgresPointRepository:
    session: AsyncSession

    async def add(self, point: Point) -> None:
        source_row = await _source_row_by_codes(
            self.session,
            point.tenant_id,
            point.asset_id,
            point.agent_id,
            point.source_id,
        )
        if source_row is None:
            raise ValueError(
                "Source "
                f"{point.tenant_id!r}/{point.asset_id!r}/"
                f"{point.agent_id!r}/{point.source_id!r} does not exist"
            )
        source, _agent, _asset, tenant = source_row
        self.session.add(
            PointModel(
                id=uuid4(),
                tenant_uuid=tenant.id,
                source_uuid=source.id,
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
        )

    async def get_by_id(self, tenant_id: str, point_id: str) -> Point | None:
        row = await _point_row_by_code(self.session, tenant_id, point_id)
        return _point_from_row(*row) if row is not None else None

    async def update(self, point: Point) -> None:
        row = await _point_row_by_code(self.session, point.tenant_id, point.point_id)
        if row is None:
            return
        model, _source, _agent, _asset, _tenant = row
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

    async def delete(self, tenant_id: str, point_id: str) -> None:
        row = await _point_row_by_code(self.session, tenant_id, point_id)
        if row is not None:
            await self.session.delete(row[0])
            await self.session.flush()

    async def delete_for_agent(
        self,
        tenant_id: str,
        asset_id: str,
        agent_id: str,
    ) -> int:
        agent_row = await _agent_row_by_codes(self.session, tenant_id, asset_id, agent_id)
        if agent_row is None:
            return 0
        agent, _asset, _tenant = agent_row
        source_ids = select(SourceModel.id).where(SourceModel.agent_uuid == agent.id)
        result = await self.session.execute(
            delete(PointModel).where(PointModel.source_uuid.in_(source_ids))
        )
        await self.session.flush()
        return _rowcount(result.rowcount)

    async def get_by_key(
        self,
        tenant_id: str,
        asset_id: str,
        agent_id: str,
        source_id: str,
        point_key: str,
    ) -> Point | None:
        row = await _point_row_by_source_and_field(
            self.session,
            tenant_id,
            asset_id,
            agent_id,
            source_id,
            "point_key",
            point_key,
        )
        return _point_from_row(*row) if row is not None else None

    async def get_by_ref(
        self,
        tenant_id: str,
        asset_id: str,
        agent_id: str,
        source_id: str,
        point_ref: str,
    ) -> Point | None:
        row = await _point_row_by_source_and_field(
            self.session,
            tenant_id,
            asset_id,
            agent_id,
            source_id,
            "point_ref",
            point_ref,
        )
        return _point_from_row(*row) if row is not None else None

    async def list_for_source(
        self,
        tenant_id: str,
        asset_id: str,
        agent_id: str,
        source_id: str,
    ) -> list[Point]:
        tenant_code = tenant_id
        asset_code = asset_id
        agent_code = agent_id
        source_code = source_id
        result = await self.session.execute(
            select(PointModel, SourceModel, AgentModel, AssetModel, TenantModel)
            .join(SourceModel, PointModel.source_uuid == SourceModel.id)
            .join(AgentModel, SourceModel.agent_uuid == AgentModel.id)
            .join(AssetModel, AgentModel.asset_uuid == AssetModel.id)
            .join(TenantModel, PointModel.tenant_uuid == TenantModel.id)
            .where(
                TenantModel.tenant_id == tenant_code,
                AssetModel.asset_id == asset_code,
                AgentModel.agent_id == agent_code,
                SourceModel.source_id == source_code,
            )
            .order_by(PointModel.point_key)
        )
        return [_point_from_row(row[0], row[1], row[2], row[3], row[4]) for row in result]


@dataclass
class PostgresAgentRuntimeConfigRevisionRepository:
    session: AsyncSession

    async def add(self, revision: AgentRuntimeConfigRevision) -> None:
        agent_row = await _agent_row_by_codes(
            self.session,
            revision.tenant_id,
            revision.asset_id,
            revision.agent_id,
        )
        if agent_row is None:
            raise ValueError(
                "Agent "
                f"{revision.tenant_id!r}/{revision.asset_id!r}/"
                f"{revision.agent_id!r} does not exist"
            )
        agent, _asset, tenant = agent_row
        self.session.add(
            AgentRuntimeConfigRevisionModel(
                id=uuid4(),
                tenant_uuid=tenant.id,
                agent_uuid=agent.id,
                config_revision=revision.config_revision,
                status=revision.status.value,
                issued_at=revision.issued_at,
                agent_runtime_payload_json=dict(revision.agent_runtime_payload_json),
                created_at=revision.created_at,
            )
        )

    async def get(
        self,
        tenant_id: str,
        asset_id: str,
        agent_id: str,
        config_revision: str,
    ) -> AgentRuntimeConfigRevision | None:
        row = await _agent_runtime_revision_row_by_codes(
            self.session,
            tenant_id,
            asset_id,
            agent_id,
            config_revision,
        )
        return _agent_runtime_config_revision_from_row(*row) if row is not None else None

    async def has_any_for_agent(
        self,
        tenant_id: str,
        asset_id: str,
        agent_id: str,
    ) -> bool:
        agent_row = await _agent_row_by_codes(self.session, tenant_id, asset_id, agent_id)
        if agent_row is None:
            return False
        agent, _asset, _tenant = agent_row
        result = await self.session.scalars(
            select(AgentRuntimeConfigRevisionModel)
            .where(AgentRuntimeConfigRevisionModel.agent_uuid == agent.id)
            .limit(1)
        )
        return result.first() is not None

    async def delete_for_agent(
        self,
        tenant_id: str,
        asset_id: str,
        agent_id: str,
    ) -> int:
        agent_row = await _agent_row_by_codes(self.session, tenant_id, asset_id, agent_id)
        if agent_row is None:
            return 0
        agent, _asset, _tenant = agent_row
        result = await self.session.execute(
            delete(AgentRuntimeConfigRevisionModel).where(
                AgentRuntimeConfigRevisionModel.agent_uuid == agent.id
            )
        )
        await self.session.flush()
        return _rowcount(result.rowcount)


@dataclass
class PostgresSourceConfigRevisionRepository:
    session: AsyncSession

    async def add(self, revision: SourceConfigRevision) -> None:
        source_row = await _source_row_by_codes(
            self.session,
            revision.tenant_id,
            revision.asset_id,
            revision.agent_id,
            revision.source_id,
        )
        if source_row is None:
            raise ValueError(
                "Source "
                f"{revision.tenant_id!r}/{revision.asset_id!r}/"
                f"{revision.agent_id!r}/{revision.source_id!r} does not exist"
            )
        runtime_row = await _agent_runtime_revision_row_by_codes(
            self.session,
            revision.tenant_id,
            revision.asset_id,
            revision.agent_id,
            revision.config_revision,
        )
        if runtime_row is None:
            raise ValueError(
                "Agent runtime config revision "
                f"{revision.config_revision!r} must exist before source revisions"
            )
        source, _agent, _asset, tenant = source_row
        runtime, _runtime_agent, _runtime_asset, _runtime_tenant = runtime_row
        self.session.add(
            SourceConfigRevisionModel(
                id=uuid4(),
                tenant_uuid=tenant.id,
                source_uuid=source.id,
                agent_runtime_config_revision_uuid=runtime.id,
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
        tenant_id: str,
        asset_id: str,
        agent_id: str,
        source_id: str,
        source_config_revision: str,
    ) -> SourceConfigRevision | None:
        row = await _source_config_revision_row_by_codes(
            self.session,
            tenant_id,
            asset_id,
            agent_id,
            source_id,
            source_config_revision,
        )
        return _source_config_revision_from_row(*row) if row is not None else None

    async def list_for_runtime_revision(
        self,
        tenant_id: str,
        asset_id: str,
        agent_id: str,
        config_revision: str,
    ) -> list[SourceConfigRevision]:
        tenant_code = tenant_id
        asset_code = asset_id
        agent_code = agent_id
        result = await self.session.execute(
            select(SourceConfigRevisionModel, SourceModel, AgentModel, AssetModel, TenantModel)
            .join(SourceModel, SourceConfigRevisionModel.source_uuid == SourceModel.id)
            .join(AgentModel, SourceModel.agent_uuid == AgentModel.id)
            .join(AssetModel, AgentModel.asset_uuid == AssetModel.id)
            .join(TenantModel, SourceConfigRevisionModel.tenant_uuid == TenantModel.id)
            .where(
                TenantModel.tenant_id == tenant_code,
                AssetModel.asset_id == asset_code,
                AgentModel.agent_id == agent_code,
                SourceConfigRevisionModel.config_revision == config_revision,
            )
            .order_by(SourceModel.source_id)
        )
        return [
            _source_config_revision_from_row(row[0], row[1], row[2], row[3], row[4])
            for row in result
        ]

    async def has_any_for_source(
        self,
        tenant_id: str,
        asset_id: str,
        agent_id: str,
        source_id: str,
    ) -> bool:
        source_row = await _source_row_by_codes(
            self.session,
            tenant_id,
            asset_id,
            agent_id,
            source_id,
        )
        if source_row is None:
            return False
        source, _agent, _asset, _tenant = source_row
        result = await self.session.scalars(
            select(SourceConfigRevisionModel)
            .where(SourceConfigRevisionModel.source_uuid == source.id)
            .limit(1)
        )
        return result.first() is not None

    async def delete_for_agent(
        self,
        tenant_id: str,
        asset_id: str,
        agent_id: str,
    ) -> int:
        agent_row = await _agent_row_by_codes(self.session, tenant_id, asset_id, agent_id)
        if agent_row is None:
            return 0
        agent, _asset, _tenant = agent_row
        source_ids = select(SourceModel.id).where(SourceModel.agent_uuid == agent.id)
        result = await self.session.execute(
            delete(SourceConfigRevisionModel).where(
                SourceConfigRevisionModel.source_uuid.in_(source_ids)
            )
        )
        await self.session.flush()
        return _rowcount(result.rowcount)


@dataclass
class PostgresConfigOutboxRepository:
    session: AsyncSession

    async def add(self, record: ConfigOutboxRecord) -> None:
        agent_row = await _agent_row_by_codes(
            self.session,
            record.tenant_id,
            record.asset_id,
            record.agent_id,
        )
        if agent_row is None:
            raise ValueError(
                "Agent "
                f"{record.tenant_id!r}/{record.asset_id!r}/{record.agent_id!r} "
                "does not exist"
            )
        source_uuid: UUID | None = None
        if record.source_id is not None:
            source_row = await _source_row_by_codes(
                self.session,
                record.tenant_id,
                record.asset_id,
                record.agent_id,
                record.source_id,
            )
            if source_row is None:
                raise ValueError(
                    "Source "
                    f"{record.tenant_id!r}/{record.asset_id!r}/"
                    f"{record.agent_id!r}/{record.source_id!r} does not exist"
                )
            source_uuid = source_row[0].id
        agent, _asset, tenant = agent_row
        self.session.add(
            ConfigOutboxModel(
                id=record.outbox_id,
                tenant_uuid=tenant.id,
                agent_uuid=agent.id,
                source_uuid=source_uuid,
                idempotency_key=record.idempotency_key,
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
        if model is None:
            return None
        return _config_outbox_from_row(
            *(await _config_outbox_row_by_model(self.session, model))
        )

    async def list_for_config_revision(
        self,
        tenant_id: str,
        asset_id: str,
        agent_id: str,
        config_revision: str,
    ) -> list[ConfigOutboxRecord]:
        tenant_code = tenant_id
        asset_code = asset_id
        agent_code = agent_id
        result = await self.session.execute(
            select(ConfigOutboxModel, TenantModel, AssetModel, AgentModel, SourceModel)
            .join(AgentModel, ConfigOutboxModel.agent_uuid == AgentModel.id)
            .join(AssetModel, AgentModel.asset_uuid == AssetModel.id)
            .join(TenantModel, ConfigOutboxModel.tenant_uuid == TenantModel.id)
            .outerjoin(SourceModel, ConfigOutboxModel.source_uuid == SourceModel.id)
            .where(
                TenantModel.tenant_id == tenant_code,
                AssetModel.asset_id == asset_code,
                AgentModel.agent_id == agent_code,
                ConfigOutboxModel.config_revision == config_revision,
            )
            .order_by(ConfigOutboxModel.config_scope)
        )
        return [
            _config_outbox_from_row(row[0], row[1], row[2], row[3], row[4])
            for row in result
        ]

    async def has_any_for_agent(
        self,
        tenant_id: str,
        asset_id: str,
        agent_id: str,
    ) -> bool:
        agent_row = await _agent_row_by_codes(self.session, tenant_id, asset_id, agent_id)
        if agent_row is None:
            return False
        agent, _asset, _tenant = agent_row
        result = await self.session.scalars(
            select(ConfigOutboxModel)
            .where(ConfigOutboxModel.agent_uuid == agent.id)
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
        source_row = await _source_row_by_codes(
            self.session,
            tenant_id,
            asset_id,
            agent_id,
            source_id,
        )
        if source_row is None:
            return False
        source, _agent, _asset, _tenant = source_row
        result = await self.session.scalars(
            select(ConfigOutboxModel)
            .where(ConfigOutboxModel.source_uuid == source.id)
            .limit(1)
        )
        return result.first() is not None

    async def delete_for_agent(
        self,
        tenant_id: str,
        asset_id: str,
        agent_id: str,
    ) -> int:
        agent_row = await _agent_row_by_codes(self.session, tenant_id, asset_id, agent_id)
        if agent_row is None:
            return 0
        agent, _asset, _tenant = agent_row
        result = await self.session.execute(
            delete(ConfigOutboxModel).where(ConfigOutboxModel.agent_uuid == agent.id)
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
            reserved.append(
                _config_outbox_from_row(
                    *(await _config_outbox_row_by_model(self.session, model))
                )
            )
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
        return _config_outbox_from_row(
            *(await _config_outbox_row_by_model(self.session, model))
        )

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
        return _config_outbox_from_row(
            *(await _config_outbox_row_by_model(self.session, model))
        )

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
        return _config_outbox_from_row(
            *(await _config_outbox_row_by_model(self.session, model))
        )

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
