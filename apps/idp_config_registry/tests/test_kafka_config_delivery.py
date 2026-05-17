from __future__ import annotations

import json
from dataclasses import dataclass, field

import pytest

from idp_config_registry.domain.entities import ConfigOutboxRecord
from idp_config_registry.infrastructure.kafka.config_delivery import (
    ConfluentKafkaConfigRecordPublisher,
)

pytestmark = pytest.mark.asyncio


@dataclass
class StubKafkaProducer:
    remaining_on_flush: int = 0
    delivery_error: str | None = None
    produced: list[dict[str, object]] = field(default_factory=list)

    def produce(
        self,
        topic: str,
        *,
        key: bytes,
        value: bytes,
        callback: object | None = None,
    ) -> None:
        self.produced.append({"topic": topic, "key": key, "value": value})
        if callable(callback):
            callback(self.delivery_error, object())

    def flush(self, timeout: float | None = None) -> int:
        return self.remaining_on_flush


async def test_kafka_config_record_publisher_serializes_outbox_record() -> None:
    producer = StubKafkaProducer()
    publisher = ConfluentKafkaConfigRecordPublisher(producer=producer)

    await publisher.publish(_outbox_record())

    assert producer.produced == [
        {
            "topic": "idp.edge.configs.v1",
            "key": b"tenant-a|asset-a|agent-a|agent_runtime",
            "value": (
                b'{"message_type":"idp.edge.config.delivery.v1",'
                b'"tenant_id":"tenant-a","payload":{"ok":true}}'
            ),
        }
    ]
    assert json.loads(producer.produced[0]["value"]) == {
        "message_type": "idp.edge.config.delivery.v1",
        "tenant_id": "tenant-a",
        "payload": {"ok": True},
    }


async def test_kafka_config_record_publisher_fails_on_delivery_error() -> None:
    producer = StubKafkaProducer(delivery_error="broker unavailable")
    publisher = ConfluentKafkaConfigRecordPublisher(producer=producer)

    with pytest.raises(RuntimeError, match="broker unavailable"):
        await publisher.publish(_outbox_record())


async def test_kafka_config_record_publisher_fails_on_flush_timeout() -> None:
    producer = StubKafkaProducer(remaining_on_flush=1)
    publisher = ConfluentKafkaConfigRecordPublisher(producer=producer)

    with pytest.raises(TimeoutError, match="timed out"):
        await publisher.publish(_outbox_record())


def _outbox_record() -> ConfigOutboxRecord:
    return ConfigOutboxRecord.new(
        tenant_code="tenant-a",
        idempotency_key="tenant-a|asset-a|agent-a|rev-001|agent_runtime",
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
            "payload": {"ok": True},
        },
    )
