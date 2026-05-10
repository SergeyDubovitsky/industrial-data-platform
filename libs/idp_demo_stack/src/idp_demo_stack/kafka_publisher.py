from __future__ import annotations

import json
from collections.abc import Callable
from typing import Protocol

from confluent_kafka import KafkaError, Producer

from idp_demo_stack.models import KafkaConfig, KafkaRecord

Output = Callable[[str], None]


class KafkaJsonPublisher(Protocol):
    def publish(self, record: KafkaRecord) -> None: ...

    def close(self) -> None: ...


class ConfluentKafkaJsonPublisher:
    def __init__(self, producer: Producer, *, output: Output = print) -> None:
        self._producer = producer
        self._output = output

    def publish(self, record: KafkaRecord) -> None:
        payload_json = json.dumps(
            record.payload,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        delivery_error: KafkaError | None = None

        def on_delivery(error: KafkaError | None, _message: object) -> None:
            nonlocal delivery_error
            delivery_error = error

        self._producer.produce(
            record.topic,
            key=record.key,
            value=payload_json,
            callback=on_delivery,
        )
        self._producer.flush(timeout=10)
        if delivery_error is not None:
            raise RuntimeError(
                f"Kafka publish failed for topic {record.topic}: {delivery_error}"
            )
        self._output(
            "PUBLISHED_KAFKA "
            f"topic={record.topic} key={record.key} payload={payload_json}"
        )

    def close(self) -> None:
        self._producer.flush(timeout=10)


def connect_kafka_publisher(
    *,
    config: KafkaConfig,
    output: Output = print,
) -> KafkaJsonPublisher:
    producer = Producer(
        {
            "bootstrap.servers": config.bootstrap_servers,
            "client.id": config.client_id,
        }
    )
    return ConfluentKafkaJsonPublisher(producer, output=output)
