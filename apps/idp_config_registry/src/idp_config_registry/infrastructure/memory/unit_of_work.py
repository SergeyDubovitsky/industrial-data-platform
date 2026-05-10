from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from types import TracebackType
from uuid import UUID

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
from idp_config_registry.domain.value_objects import ConfigOutboxStatus


@dataclass
class InMemoryTenantRepository:
    _items: dict[str, Tenant] = field(default_factory=dict)

    async def add(self, tenant: Tenant) -> None:
        self._items[tenant.tenant_id] = tenant

    async def get(self, tenant_id: str) -> Tenant | None:
        return self._items.get(tenant_id)

    async def update(self, tenant: Tenant) -> None:
        self._items[tenant.tenant_id] = tenant

    async def delete(self, tenant_id: str) -> None:
        self._items.pop(tenant_id, None)

    async def list(self) -> list[Tenant]:
        return sorted(self._items.values(), key=lambda tenant: tenant.tenant_id)


@dataclass
class InMemoryAssetRepository:
    _items: dict[tuple[str, str], Asset] = field(default_factory=dict)

    async def add(self, asset: Asset) -> None:
        self._items[(asset.tenant_id, asset.asset_id)] = asset

    async def get(self, tenant_id: str, asset_id: str) -> Asset | None:
        return self._items.get((tenant_id, asset_id))

    async def update(self, asset: Asset) -> None:
        self._items[(asset.tenant_id, asset.asset_id)] = asset

    async def delete(self, tenant_id: str, asset_id: str) -> None:
        self._items.pop((tenant_id, asset_id), None)

    async def list_for_tenant(self, tenant_id: str) -> list[Asset]:
        return sorted(
            (
                asset
                for (asset_tenant_id, _), asset in self._items.items()
                if asset_tenant_id == tenant_id
            ),
            key=lambda asset: asset.asset_id,
        )


@dataclass
class InMemoryAgentRepository:
    _items: dict[tuple[str, str, str], Agent] = field(default_factory=dict)

    async def add(self, agent: Agent) -> None:
        self._items[(agent.tenant_id, agent.asset_id, agent.agent_id)] = agent

    async def get(self, tenant_id: str, asset_id: str, agent_id: str) -> Agent | None:
        return self._items.get((tenant_id, asset_id, agent_id))

    async def update(self, agent: Agent) -> None:
        self._items[(agent.tenant_id, agent.asset_id, agent.agent_id)] = agent

    async def delete(self, tenant_id: str, asset_id: str, agent_id: str) -> None:
        self._items.pop((tenant_id, asset_id, agent_id), None)

    async def list_for_asset(self, tenant_id: str, asset_id: str) -> list[Agent]:
        return sorted(
            (
                agent
                for (agent_tenant_id, agent_asset_id, _), agent in self._items.items()
                if agent_tenant_id == tenant_id and agent_asset_id == asset_id
            ),
            key=lambda agent: agent.agent_id,
        )


@dataclass
class InMemorySourceRepository:
    _items: dict[tuple[str, str, str, str], Source] = field(default_factory=dict)

    async def add(self, source: Source) -> None:
        self._items[
            (
                source.tenant_id,
                source.asset_id,
                source.agent_id,
                source.source_id,
            )
        ] = source

    async def get(
        self,
        tenant_id: str,
        asset_id: str,
        agent_id: str,
        source_id: str,
    ) -> Source | None:
        return self._items.get((tenant_id, asset_id, agent_id, source_id))

    async def update(self, source: Source) -> None:
        self._items[
            (
                source.tenant_id,
                source.asset_id,
                source.agent_id,
                source.source_id,
            )
        ] = source

    async def delete(
        self,
        tenant_id: str,
        asset_id: str,
        agent_id: str,
        source_id: str,
    ) -> None:
        self._items.pop((tenant_id, asset_id, agent_id, source_id), None)

    async def list_for_agent(
        self,
        tenant_id: str,
        asset_id: str,
        agent_id: str,
    ) -> list[Source]:
        return sorted(
            (
                source
                for (
                    source_tenant_id,
                    source_asset_id,
                    source_agent_id,
                    _,
                ), source in self._items.items()
                if source_tenant_id == tenant_id
                and source_asset_id == asset_id
                and source_agent_id == agent_id
            ),
            key=lambda source: source.source_id,
        )


@dataclass
class InMemoryPointRepository:
    _items: dict[tuple[str, str], Point] = field(default_factory=dict)

    async def add(self, point: Point) -> None:
        self._items[(point.tenant_id, point.point_id)] = point

    async def get_by_id(self, tenant_id: str, point_id: str) -> Point | None:
        return self._items.get((tenant_id, point_id))

    async def update(self, point: Point) -> None:
        self._items[(point.tenant_id, point.point_id)] = point

    async def delete(self, tenant_id: str, point_id: str) -> None:
        self._items.pop((tenant_id, point_id), None)

    async def get_by_key(
        self,
        tenant_id: str,
        asset_id: str,
        agent_id: str,
        source_id: str,
        point_key: str,
    ) -> Point | None:
        for point in self._items.values():
            if (
                point.tenant_id == tenant_id
                and point.asset_id == asset_id
                and point.agent_id == agent_id
                and point.source_id == source_id
                and point.point_key == point_key
            ):
                return point
        return None

    async def get_by_ref(
        self,
        tenant_id: str,
        asset_id: str,
        agent_id: str,
        source_id: str,
        point_ref: str,
    ) -> Point | None:
        for point in self._items.values():
            if (
                point.tenant_id == tenant_id
                and point.asset_id == asset_id
                and point.agent_id == agent_id
                and point.source_id == source_id
                and point.point_ref == point_ref
            ):
                return point
        return None

    async def list_for_source(
        self,
        tenant_id: str,
        asset_id: str,
        agent_id: str,
        source_id: str,
    ) -> list[Point]:
        return sorted(
            (
                point
                for point in self._items.values()
                if point.tenant_id == tenant_id
                and point.asset_id == asset_id
                and point.agent_id == agent_id
                and point.source_id == source_id
            ),
            key=lambda point: point.point_key,
        )


@dataclass
class InMemoryAgentRuntimeConfigRevisionRepository:
    _items: dict[tuple[str, str, str, str], AgentRuntimeConfigRevision] = field(
        default_factory=dict
    )

    async def add(self, revision: AgentRuntimeConfigRevision) -> None:
        self._items[
            (
                revision.tenant_id,
                revision.asset_id,
                revision.agent_id,
                revision.config_revision,
            )
        ] = revision

    async def get(
        self,
        tenant_id: str,
        asset_id: str,
        agent_id: str,
        config_revision: str,
    ) -> AgentRuntimeConfigRevision | None:
        return self._items.get((tenant_id, asset_id, agent_id, config_revision))

    async def has_any_for_agent(
        self,
        tenant_id: str,
        asset_id: str,
        agent_id: str,
    ) -> bool:
        return any(
            revision.tenant_id == tenant_id
            and revision.asset_id == asset_id
            and revision.agent_id == agent_id
            for revision in self._items.values()
        )


@dataclass
class InMemorySourceConfigRevisionRepository:
    _items: dict[tuple[str, str, str, str, str], SourceConfigRevision] = field(
        default_factory=dict
    )

    async def add(self, revision: SourceConfigRevision) -> None:
        self._items[
            (
                revision.tenant_id,
                revision.asset_id,
                revision.agent_id,
                revision.source_id,
                revision.source_config_revision,
            )
        ] = revision

    async def get(
        self,
        tenant_id: str,
        asset_id: str,
        agent_id: str,
        source_id: str,
        source_config_revision: str,
    ) -> SourceConfigRevision | None:
        return self._items.get(
            (tenant_id, asset_id, agent_id, source_id, source_config_revision)
        )

    async def list_for_runtime_revision(
        self,
        tenant_id: str,
        asset_id: str,
        agent_id: str,
        config_revision: str,
    ) -> list[SourceConfigRevision]:
        return sorted(
            (
                revision
                for revision in self._items.values()
                if revision.tenant_id == tenant_id
                and revision.asset_id == asset_id
                and revision.agent_id == agent_id
                and revision.config_revision == config_revision
            ),
            key=lambda revision: revision.source_id,
        )

    async def has_any_for_source(
        self,
        tenant_id: str,
        asset_id: str,
        agent_id: str,
        source_id: str,
    ) -> bool:
        return any(
            revision.tenant_id == tenant_id
            and revision.asset_id == asset_id
            and revision.agent_id == agent_id
            and revision.source_id == source_id
            for revision in self._items.values()
        )


@dataclass
class InMemoryConfigOutboxRepository:
    _items: dict[str, ConfigOutboxRecord] = field(default_factory=dict)

    async def add(self, record: ConfigOutboxRecord) -> None:
        self._items[record.idempotency_key] = record

    async def get_by_idempotency_key(
        self,
        idempotency_key: str,
    ) -> ConfigOutboxRecord | None:
        return self._items.get(idempotency_key)

    async def list_for_config_revision(
        self,
        tenant_id: str,
        asset_id: str,
        agent_id: str,
        config_revision: str,
    ) -> list[ConfigOutboxRecord]:
        return sorted(
            (
                record
                for record in self._items.values()
                if record.tenant_id == tenant_id
                and record.asset_id == asset_id
                and record.agent_id == agent_id
                and record.config_revision == config_revision
            ),
            key=lambda record: record.config_scope,
        )

    async def has_any_for_agent(
        self,
        tenant_id: str,
        asset_id: str,
        agent_id: str,
    ) -> bool:
        return any(
            record.tenant_id == tenant_id
            and record.asset_id == asset_id
            and record.agent_id == agent_id
            for record in self._items.values()
        )

    async def has_any_for_source(
        self,
        tenant_id: str,
        asset_id: str,
        agent_id: str,
        source_id: str,
    ) -> bool:
        return any(
            record.tenant_id == tenant_id
            and record.asset_id == asset_id
            and record.agent_id == agent_id
            and record.source_id == source_id
            for record in self._items.values()
        )

    async def reserve_available(
        self,
        *,
        limit: int,
        now: datetime,
        lease_duration: timedelta,
    ) -> list[ConfigOutboxRecord]:
        candidates = sorted(
            (
                record
                for record in self._items.values()
                if record.status in (
                    ConfigOutboxStatus.PENDING,
                    ConfigOutboxStatus.RETRY,
                )
                and record.available_at <= now
                and (
                    record.next_attempt_at is None
                    or record.next_attempt_at <= now
                )
            ),
            key=lambda record: (record.available_at, record.created_at),
        )[:limit]
        reserved = [record.reserve(now=now, lease_duration=lease_duration) for record in candidates]
        for record in reserved:
            self._items[record.idempotency_key] = record
        return reserved

    async def mark_published(
        self,
        outbox_id: UUID,
        *,
        now: datetime,
    ) -> ConfigOutboxRecord | None:
        record = self._record_by_id(outbox_id)
        if record is None:
            return None
        updated = record.mark_published(now=now)
        self._items[updated.idempotency_key] = updated
        return updated

    async def mark_retry(
        self,
        outbox_id: UUID,
        *,
        now: datetime,
        error: str,
        next_attempt_at: datetime,
    ) -> ConfigOutboxRecord | None:
        record = self._record_by_id(outbox_id)
        if record is None:
            return None
        updated = record.mark_retry(
            now=now,
            error=error,
            next_attempt_at=next_attempt_at,
        )
        self._items[updated.idempotency_key] = updated
        return updated

    async def mark_dead_letter(
        self,
        outbox_id: UUID,
        *,
        now: datetime,
        error: str,
    ) -> ConfigOutboxRecord | None:
        record = self._record_by_id(outbox_id)
        if record is None:
            return None
        updated = record.mark_dead_letter(now=now, error=error)
        self._items[updated.idempotency_key] = updated
        return updated

    async def release_expired_leases(
        self,
        *,
        now: datetime,
    ) -> int:
        released = 0
        for record in tuple(self._items.values()):
            if (
                record.status == ConfigOutboxStatus.INFLIGHT
                and record.lease_expires_at is not None
                and record.lease_expires_at <= now
            ):
                updated = record.release_expired_lease(now=now)
                self._items[updated.idempotency_key] = updated
                released += 1
        return released

    def _record_by_id(self, outbox_id: UUID) -> ConfigOutboxRecord | None:
        for record in self._items.values():
            if record.outbox_id == outbox_id:
                return record
        return None


@dataclass
class InMemoryUnitOfWork:
    tenants: InMemoryTenantRepository
    assets: InMemoryAssetRepository
    agents: InMemoryAgentRepository
    sources: InMemorySourceRepository
    points: InMemoryPointRepository
    agent_runtime_config_revisions: InMemoryAgentRuntimeConfigRevisionRepository
    source_config_revisions: InMemorySourceConfigRevisionRepository
    config_outbox: InMemoryConfigOutboxRepository
    committed: bool = False

    async def __aenter__(self) -> InMemoryUnitOfWork:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    async def commit(self) -> None:
        self.committed = True


@dataclass
class InMemoryUnitOfWorkFactory:
    tenants: InMemoryTenantRepository = field(default_factory=InMemoryTenantRepository)
    assets: InMemoryAssetRepository = field(default_factory=InMemoryAssetRepository)
    agents: InMemoryAgentRepository = field(default_factory=InMemoryAgentRepository)
    sources: InMemorySourceRepository = field(default_factory=InMemorySourceRepository)
    points: InMemoryPointRepository = field(default_factory=InMemoryPointRepository)
    agent_runtime_config_revisions: InMemoryAgentRuntimeConfigRevisionRepository = field(
        default_factory=InMemoryAgentRuntimeConfigRevisionRepository
    )
    source_config_revisions: InMemorySourceConfigRevisionRepository = field(
        default_factory=InMemorySourceConfigRevisionRepository
    )
    config_outbox: InMemoryConfigOutboxRepository = field(
        default_factory=InMemoryConfigOutboxRepository
    )

    def __call__(self) -> InMemoryUnitOfWork:
        return InMemoryUnitOfWork(
            tenants=self.tenants,
            assets=self.assets,
            agents=self.agents,
            sources=self.sources,
            points=self.points,
            agent_runtime_config_revisions=self.agent_runtime_config_revisions,
            source_config_revisions=self.source_config_revisions,
            config_outbox=self.config_outbox,
        )
