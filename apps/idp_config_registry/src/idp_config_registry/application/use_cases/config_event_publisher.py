from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from idp_config_registry.application.ports.config_delivery import ConfigRecordPublisher
from idp_config_registry.application.ports.unit_of_work import UnitOfWork

UnitOfWorkFactory = Callable[[], UnitOfWork]


@dataclass(frozen=True)
class PublishConfigOutboxBatchCommand:
    now: datetime
    limit: int
    lease_duration: timedelta
    retry_delay: timedelta
    max_attempts: int


@dataclass(frozen=True)
class PublishConfigOutboxBatchResult:
    reserved: int
    published: int
    retried: int
    dead_lettered: int


class PublishConfigOutboxBatch:
    def __init__(
        self,
        unit_of_work_factory: UnitOfWorkFactory,
        publisher: ConfigRecordPublisher,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._publisher = publisher

    async def execute(
        self,
        command: PublishConfigOutboxBatchCommand,
    ) -> PublishConfigOutboxBatchResult:
        async with self._unit_of_work_factory() as unit_of_work:
            records = await unit_of_work.config_outbox.reserve_available(
                limit=command.limit,
                now=command.now,
                lease_duration=command.lease_duration,
            )
            await unit_of_work.commit()

        published = 0
        retried = 0
        dead_lettered = 0
        for record in records:
            try:
                await self._publisher.publish(record)
            except Exception as exc:  # noqa: BLE001 - publisher errors become outbox state.
                if record.attempt_count + 1 >= command.max_attempts:
                    await _mark_dead_letter(
                        self._unit_of_work_factory,
                        record.outbox_id,
                        now=command.now,
                        error=str(exc),
                    )
                    dead_lettered += 1
                else:
                    await _mark_retry(
                        self._unit_of_work_factory,
                        record.outbox_id,
                        now=command.now,
                        error=str(exc),
                        next_attempt_at=command.now + command.retry_delay,
                    )
                    retried += 1
            else:
                await _mark_published(
                    self._unit_of_work_factory,
                    record.outbox_id,
                    now=command.now,
                )
                published += 1

        return PublishConfigOutboxBatchResult(
            reserved=len(records),
            published=published,
            retried=retried,
            dead_lettered=dead_lettered,
        )


async def _mark_published(
    unit_of_work_factory: UnitOfWorkFactory,
    outbox_id: UUID,
    *,
    now: datetime,
) -> None:
    async with unit_of_work_factory() as active_unit_of_work:
        await active_unit_of_work.config_outbox.mark_published(
            outbox_id,
            now=now,
        )
        await active_unit_of_work.commit()


async def _mark_retry(
    unit_of_work_factory: UnitOfWorkFactory,
    outbox_id: UUID,
    *,
    now: datetime,
    error: str,
    next_attempt_at: datetime,
) -> None:
    async with unit_of_work_factory() as active_unit_of_work:
        await active_unit_of_work.config_outbox.mark_retry(
            outbox_id,
            now=now,
            error=error,
            next_attempt_at=next_attempt_at,
        )
        await active_unit_of_work.commit()


async def _mark_dead_letter(
    unit_of_work_factory: UnitOfWorkFactory,
    outbox_id: UUID,
    *,
    now: datetime,
    error: str,
) -> None:
    async with unit_of_work_factory() as active_unit_of_work:
        await active_unit_of_work.config_outbox.mark_dead_letter(
            outbox_id,
            now=now,
            error=error,
        )
        await active_unit_of_work.commit()
