from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from idp_config_registry.application.use_cases.config_outbox import (
    MarkConfigOutboxDeadLetter,
    MarkConfigOutboxDeadLetterCommand,
    MarkConfigOutboxPublished,
    MarkConfigOutboxRetry,
    MarkConfigOutboxRetryCommand,
    ReleaseExpiredConfigOutboxLeases,
    ReserveConfigOutboxCommand,
    ReserveConfigOutboxRecords,
)
from idp_config_registry.domain.entities import ConfigOutboxRecord
from idp_config_registry.domain.value_objects import ConfigOutboxStatus
from idp_config_registry.infrastructure.memory.unit_of_work import (
    InMemoryUnitOfWorkFactory,
)

pytestmark = pytest.mark.asyncio


async def test_reserve_config_outbox_records_leases_available_records() -> None:
    unit_of_work_factory = InMemoryUnitOfWorkFactory()
    await _add_outbox_record(unit_of_work_factory, idempotency_key="record-1")
    now = datetime(2026, 5, 3, 10, 0, tzinfo=UTC)

    records = await ReserveConfigOutboxRecords(unit_of_work_factory()).execute(
        ReserveConfigOutboxCommand(
            limit=10,
            now=now,
            lease_duration=timedelta(seconds=30),
        )
    )

    assert len(records) == 1
    assert records[0].status == ConfigOutboxStatus.INFLIGHT
    assert records[0].lease_expires_at == now + timedelta(seconds=30)


async def test_reserve_config_outbox_records_skips_future_retry() -> None:
    unit_of_work_factory = InMemoryUnitOfWorkFactory()
    now = datetime(2026, 5, 3, 10, 0, tzinfo=UTC)
    record = _outbox_record(idempotency_key="record-1").mark_retry(
        now=now,
        error="kafka unavailable",
        next_attempt_at=now + timedelta(minutes=5),
    )
    await _add_outbox_record(unit_of_work_factory, record=record)

    records = await ReserveConfigOutboxRecords(unit_of_work_factory()).execute(
        ReserveConfigOutboxCommand(
            limit=10,
            now=now,
            lease_duration=timedelta(seconds=30),
        )
    )

    assert records == []


async def test_mark_config_outbox_published_clears_lease() -> None:
    unit_of_work_factory = InMemoryUnitOfWorkFactory()
    now = datetime(2026, 5, 3, 10, 0, tzinfo=UTC)
    await _add_outbox_record(unit_of_work_factory, idempotency_key="record-1")
    reserved = await ReserveConfigOutboxRecords(unit_of_work_factory()).execute(
        ReserveConfigOutboxCommand(
            limit=1,
            now=now,
            lease_duration=timedelta(seconds=30),
        )
    )

    published = await MarkConfigOutboxPublished(unit_of_work_factory()).execute(
        reserved[0].outbox_id,
        now=now + timedelta(seconds=5),
    )

    assert published is not None
    assert published.status == ConfigOutboxStatus.PUBLISHED
    assert published.lease_expires_at is None
    assert published.published_at == now + timedelta(seconds=5)


async def test_mark_config_outbox_retry_records_error_and_next_attempt() -> None:
    unit_of_work_factory = InMemoryUnitOfWorkFactory()
    now = datetime(2026, 5, 3, 10, 0, tzinfo=UTC)
    await _add_outbox_record(unit_of_work_factory, idempotency_key="record-1")
    reserved = await ReserveConfigOutboxRecords(unit_of_work_factory()).execute(
        ReserveConfigOutboxCommand(
            limit=1,
            now=now,
            lease_duration=timedelta(seconds=30),
        )
    )

    retry = await MarkConfigOutboxRetry(unit_of_work_factory()).execute(
        MarkConfigOutboxRetryCommand(
            outbox_id=reserved[0].outbox_id,
            now=now + timedelta(seconds=5),
            error="kafka unavailable",
            next_attempt_at=now + timedelta(minutes=1),
        )
    )

    assert retry is not None
    assert retry.status == ConfigOutboxStatus.RETRY
    assert retry.attempt_count == 1
    assert retry.last_error == "kafka unavailable"
    assert retry.next_attempt_at == now + timedelta(minutes=1)


async def test_mark_config_outbox_dead_letter_records_final_error() -> None:
    unit_of_work_factory = InMemoryUnitOfWorkFactory()
    now = datetime(2026, 5, 3, 10, 0, tzinfo=UTC)
    record = _outbox_record(idempotency_key="record-1")
    await _add_outbox_record(unit_of_work_factory, record=record)

    dead_letter = await MarkConfigOutboxDeadLetter(unit_of_work_factory()).execute(
        MarkConfigOutboxDeadLetterCommand(
            outbox_id=record.outbox_id,
            now=now,
            error="schema violation",
        )
    )

    assert dead_letter is not None
    assert dead_letter.status == ConfigOutboxStatus.DEAD_LETTER
    assert dead_letter.attempt_count == 1
    assert dead_letter.last_error == "schema violation"


async def test_release_expired_config_outbox_leases_returns_records_to_retry() -> None:
    unit_of_work_factory = InMemoryUnitOfWorkFactory()
    now = datetime(2026, 5, 3, 10, 0, tzinfo=UTC)
    await _add_outbox_record(unit_of_work_factory, idempotency_key="record-1")
    reserved = await ReserveConfigOutboxRecords(unit_of_work_factory()).execute(
        ReserveConfigOutboxCommand(
            limit=1,
            now=now,
            lease_duration=timedelta(seconds=30),
        )
    )

    released = await ReleaseExpiredConfigOutboxLeases(
        unit_of_work_factory()
    ).execute(now=now + timedelta(seconds=31))
    record = await unit_of_work_factory.config_outbox.get_by_idempotency_key(
        reserved[0].idempotency_key
    )

    assert released == 1
    assert record is not None
    assert record.status == ConfigOutboxStatus.RETRY
    assert record.lease_expires_at is None
    assert record.next_attempt_at == now + timedelta(seconds=31)


def _outbox_record(
    *,
    idempotency_key: str,
) -> ConfigOutboxRecord:
    created_at = datetime(2026, 5, 3, 9, 59, tzinfo=UTC)
    return ConfigOutboxRecord.new(
        tenant_code="tenant-a",
        idempotency_key=idempotency_key,
        asset_code="asset-a",
        agent_code="agent-a",
        config_revision="rev-001",
        config_scope="agent_runtime",
        source_code=None,
        source_config_revision=None,
        kafka_key="tenant-a|asset-a|agent-a|agent_runtime",
        payload_json={
            "message_type": "idp.edge.config.delivery.v1",
            "tenant_id": "tenant-a",
            "asset_id": "asset-a",
            "agent_id": "agent-a",
            "config_revision": "rev-001",
            "config_scope": "agent_runtime",
            "source_id": None,
            "source_config_revision": None,
            "target_mqtt_topic": "idp/v1/agents/agent-a/config/agent-runtime",
            "mqtt_retain": True,
            "mqtt_qos": 1,
            "operation": "upsert",
            "payload_message_type": "idp.edge.agent-runtime-config.v1",
            "payload": {},
            "idempotency_key": idempotency_key,
            "issued_at": "2026-05-03T10:00:00Z",
        },
    )._replace(
        available_at=created_at,
        created_at=created_at,
        updated_at=created_at,
    )


async def _add_outbox_record(
    unit_of_work_factory: InMemoryUnitOfWorkFactory,
    *,
    idempotency_key: str = "record-1",
    record: ConfigOutboxRecord | None = None,
) -> None:
    async with unit_of_work_factory() as unit_of_work:
        await unit_of_work.config_outbox.add(
            record or _outbox_record(idempotency_key=idempotency_key)
        )
        await unit_of_work.commit()
