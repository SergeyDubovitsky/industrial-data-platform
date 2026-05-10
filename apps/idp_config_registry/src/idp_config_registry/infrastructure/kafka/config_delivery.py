from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Protocol

from confluent_kafka import Producer

from idp_config_registry.domain.entities import ConfigOutboxRecord


class KafkaProducerClient(Protocol):
    def produce(
        self,
        topic: str,
        *,
        key: bytes,
        value: bytes,
        callback: object | None = None,
    ) -> None: ...

    def flush(self, timeout: float | None = None) -> int: ...


@dataclass(frozen=True)
class ConfluentKafkaConfigRecordPublisher:
    producer: KafkaProducerClient
    flush_timeout_seconds: float = 10.0

    @classmethod
    def from_bootstrap_servers(
        cls,
        bootstrap_servers: str,
        *,
        client_id: str = "idp-config-registry",
        flush_timeout_seconds: float = 10.0,
    ) -> ConfluentKafkaConfigRecordPublisher:
        return cls(
            producer=Producer(
                {
                    "bootstrap.servers": bootstrap_servers,
                    "client.id": client_id,
                    "acks": "all",
                }
            ),
            flush_timeout_seconds=flush_timeout_seconds,
        )

    async def publish(self, record: ConfigOutboxRecord) -> None:
        await asyncio.to_thread(self._publish_sync, record)

    def _publish_sync(self, record: ConfigOutboxRecord) -> None:
        delivery_error: list[BaseException] = []

        def on_delivery(error: object, message: object) -> None:
            if error is not None:
                delivery_error.append(RuntimeError(str(error)))

        self.producer.produce(
            record.kafka_topic,
            key=record.kafka_key.encode("utf-8"),
            value=json.dumps(
                record.payload_json,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8"),
            callback=on_delivery,
        )
        remaining = self.producer.flush(timeout=self.flush_timeout_seconds)
        if remaining:
            raise TimeoutError(
                f"Kafka publish timed out with {remaining} message(s) remaining"
            )
        if delivery_error:
            raise delivery_error[0]
