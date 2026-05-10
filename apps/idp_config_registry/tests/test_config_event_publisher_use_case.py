from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import pytest

from idp_config_registry.application.use_cases.config_event_publisher import (
    PublishConfigOutboxBatch,
    PublishConfigOutboxBatchCommand,
)
from idp_config_registry.domain.entities import ConfigOutboxRecord
from idp_config_registry.domain.value_objects import ConfigOutboxStatus
from idp_config_registry.infrastructure.memory.unit_of_work import (
    InMemoryUnitOfWorkFactory,
)

pytestmark = pytest.mark.asyncio


@dataclass
class RecordingPublisher:
    fail_keys: set[str] = field(default_factory=set)
    published: list[ConfigOutboxRecord] = field(default_factory=list)

    async def publish(self, record: ConfigOutboxRecord) -> None:
        if record.idempotency_key in self.fail_keys:
            raise RuntimeError("kafka unavailable")
        self.published.append(record)


async def test_publish_config_outbox_batch_marks_successful_records_published() -> None:
    unit_of_work_factory = InMemoryUnitOfWorkFactory()
    await _add_record(unit_of_work_factory, idempotency_key="record-1")
    publisher = RecordingPublisher()
    now = datetime(2026, 5, 3, 10, 0, tzinfo=UTC)

    result = await PublishConfigOutboxBatch(
        unit_of_work_factory,
        publisher,
    ).execute(_command(now))
    record = await unit_of_work_factory.config_outbox.get_by_idempotency_key(
        "record-1"
    )

    assert result.reserved == 1
    assert result.published == 1
    assert result.retried == 0
    assert result.dead_lettered == 0
    assert [record.idempotency_key for record in publisher.published] == ["record-1"]
    assert record is not None
    assert record.status == ConfigOutboxStatus.PUBLISHED
    assert record.published_at == now


async def test_publish_config_outbox_batch_retries_transient_failures() -> None:
    unit_of_work_factory = InMemoryUnitOfWorkFactory()
    await _add_record(unit_of_work_factory, idempotency_key="record-1")
    publisher = RecordingPublisher(fail_keys={"record-1"})
    now = datetime(2026, 5, 3, 10, 0, tzinfo=UTC)

    result = await PublishConfigOutboxBatch(
        unit_of_work_factory,
        publisher,
    ).execute(_command(now, max_attempts=3))
    record = await unit_of_work_factory.config_outbox.get_by_idempotency_key(
        "record-1"
    )

    assert result.reserved == 1
    assert result.published == 0
    assert result.retried == 1
    assert result.dead_lettered == 0
    assert record is not None
    assert record.status == ConfigOutboxStatus.RETRY
    assert record.attempt_count == 1
    assert record.last_error == "kafka unavailable"
    assert record.next_attempt_at == now + timedelta(seconds=30)


async def test_publish_config_outbox_batch_dead_letters_after_max_attempts() -> None:
    unit_of_work_factory = InMemoryUnitOfWorkFactory()
    now = datetime(2026, 5, 3, 10, 0, tzinfo=UTC)
    record = (
        _outbox_record(idempotency_key="record-1")
        .mark_retry(
            now=now - timedelta(minutes=2),
            error="previous failure",
            next_attempt_at=now - timedelta(minutes=1),
        )
        .mark_retry(
            now=now - timedelta(minutes=1),
            error="previous failure",
            next_attempt_at=now,
        )
    )
    await _add_record(unit_of_work_factory, record=record)
    publisher = RecordingPublisher(fail_keys={"record-1"})

    result = await PublishConfigOutboxBatch(
        unit_of_work_factory,
        publisher,
    ).execute(_command(now, max_attempts=3))
    stored = await unit_of_work_factory.config_outbox.get_by_idempotency_key(
        "record-1"
    )

    assert result.reserved == 1
    assert result.published == 0
    assert result.retried == 0
    assert result.dead_lettered == 1
    assert stored is not None
    assert stored.status == ConfigOutboxStatus.DEAD_LETTER
    assert stored.attempt_count == 3
    assert stored.last_error == "kafka unavailable"


async def test_publish_config_outbox_batch_continues_after_one_failure() -> None:
    unit_of_work_factory = InMemoryUnitOfWorkFactory()
    await _add_record(unit_of_work_factory, idempotency_key="record-1")
    await _add_record(unit_of_work_factory, idempotency_key="record-2")
    publisher = RecordingPublisher(fail_keys={"record-1"})
    now = datetime(2026, 5, 3, 10, 0, tzinfo=UTC)

    result = await PublishConfigOutboxBatch(
        unit_of_work_factory,
        publisher,
    ).execute(_command(now, max_attempts=3))
    failed = await unit_of_work_factory.config_outbox.get_by_idempotency_key(
        "record-1"
    )
    succeeded = await unit_of_work_factory.config_outbox.get_by_idempotency_key(
        "record-2"
    )

    assert result.reserved == 2
    assert result.published == 1
    assert result.retried == 1
    assert result.dead_lettered == 0
    assert failed is not None
    assert failed.status == ConfigOutboxStatus.RETRY
    assert succeeded is not None
    assert succeeded.status == ConfigOutboxStatus.PUBLISHED


def _command(
    now: datetime,
    *,
    max_attempts: int = 3,
) -> PublishConfigOutboxBatchCommand:
    return PublishConfigOutboxBatchCommand(
        now=now,
        limit=10,
        lease_duration=timedelta(seconds=30),
        retry_delay=timedelta(seconds=30),
        max_attempts=max_attempts,
    )


def _outbox_record(*, idempotency_key: str) -> ConfigOutboxRecord:
    created_at = datetime(2026, 5, 3, 9, 59, tzinfo=UTC)
    return ConfigOutboxRecord.new(
        tenant_id="tenant-a",
        idempotency_key=idempotency_key,
        asset_id="asset-a",
        agent_id="agent-a",
        config_revision="rev-001",
        config_scope="agent_runtime",
        source_id=None,
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


async def _add_record(
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
