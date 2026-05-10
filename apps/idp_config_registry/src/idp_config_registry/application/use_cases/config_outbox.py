from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from idp_config_registry.application.ports.unit_of_work import UnitOfWork
from idp_config_registry.domain.entities import ConfigOutboxRecord


@dataclass(frozen=True)
class ReserveConfigOutboxCommand:
    limit: int
    now: datetime
    lease_duration: timedelta


@dataclass(frozen=True)
class MarkConfigOutboxRetryCommand:
    outbox_id: UUID
    now: datetime
    error: str
    next_attempt_at: datetime


@dataclass(frozen=True)
class MarkConfigOutboxDeadLetterCommand:
    outbox_id: UUID
    now: datetime
    error: str


class ReserveConfigOutboxRecords:
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        self._unit_of_work = unit_of_work

    async def execute(
        self,
        command: ReserveConfigOutboxCommand,
    ) -> list[ConfigOutboxRecord]:
        async with self._unit_of_work as unit_of_work:
            records = await unit_of_work.config_outbox.reserve_available(
                limit=command.limit,
                now=command.now,
                lease_duration=command.lease_duration,
            )
            await unit_of_work.commit()
            return records


class MarkConfigOutboxPublished:
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        self._unit_of_work = unit_of_work

    async def execute(
        self,
        outbox_id: UUID,
        *,
        now: datetime,
    ) -> ConfigOutboxRecord | None:
        async with self._unit_of_work as unit_of_work:
            record = await unit_of_work.config_outbox.mark_published(
                outbox_id,
                now=now,
            )
            await unit_of_work.commit()
            return record


class MarkConfigOutboxRetry:
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        self._unit_of_work = unit_of_work

    async def execute(
        self,
        command: MarkConfigOutboxRetryCommand,
    ) -> ConfigOutboxRecord | None:
        async with self._unit_of_work as unit_of_work:
            record = await unit_of_work.config_outbox.mark_retry(
                command.outbox_id,
                now=command.now,
                error=command.error,
                next_attempt_at=command.next_attempt_at,
            )
            await unit_of_work.commit()
            return record


class MarkConfigOutboxDeadLetter:
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        self._unit_of_work = unit_of_work

    async def execute(
        self,
        command: MarkConfigOutboxDeadLetterCommand,
    ) -> ConfigOutboxRecord | None:
        async with self._unit_of_work as unit_of_work:
            record = await unit_of_work.config_outbox.mark_dead_letter(
                command.outbox_id,
                now=command.now,
                error=command.error,
            )
            await unit_of_work.commit()
            return record


class ReleaseExpiredConfigOutboxLeases:
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        self._unit_of_work = unit_of_work

    async def execute(self, *, now: datetime) -> int:
        async with self._unit_of_work as unit_of_work:
            released = await unit_of_work.config_outbox.release_expired_leases(now=now)
            await unit_of_work.commit()
            return released
