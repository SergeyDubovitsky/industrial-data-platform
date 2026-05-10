from __future__ import annotations

import json
from datetime import UTC, datetime

from edge_telemetry_agent.application.configuration import build_agent_runtime_config
from edge_telemetry_agent.application.delivery import DeliveryWorker
from edge_telemetry_agent.domain.events import MqttPublication, TelemetryEvent


class FakePublisher:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.publications: list[MqttPublication] = []

    def publish(self, publication: MqttPublication) -> None:
        if self.fail:
            raise RuntimeError("publish failed")
        self.publications.append(publication)


class FakeOutboxRecord:
    def __init__(self, *, record_id: int, payload_json: str, attempt_count: int) -> None:
        self.id = record_id
        self.payload_json = payload_json
        self.attempt_count = attempt_count


class FakeOutbox:
    def __init__(self, records: list[FakeOutboxRecord]) -> None:
        self.records = records
        self.sent_ids: list[int] = []
        self.retries: list[tuple[int, datetime, str]] = []
        self.dead_letters: list[tuple[int, str]] = []

    def reserve_batch(
        self,
        *,
        limit: int = 100,
        now: datetime | None = None,
        lease_seconds: int = 60,
    ) -> list[FakeOutboxRecord]:
        return self.records[:limit]

    def mark_sent(self, record_id: int) -> None:
        self.sent_ids.append(record_id)

    def mark_retry(self, record_id: int, *, retry_at: datetime, error: str) -> None:
        self.retries.append((record_id, retry_at, error))

    def mark_dead_letter(self, record_id: int, *, error: str) -> None:
        self.dead_letters.append((record_id, error))


def _runtime_config():
    return build_agent_runtime_config(
        bootstrap_data={
            "agent_id": "edge-telemetry-agent-001",
            "delivery": {
                "transport": "mqtt",
                "mqtt": {
                    "enabled": True,
                    "version": "5.0",
                    "broker": "mqtt://127.0.0.1:1883",
                    "topic_root": "idp/v1",
                    "client_id_prefix": "edge-telemetry-agent",
                    "username_env": "EDGE_AGENT_MQTT_USERNAME",
                    "password_env": "EDGE_AGENT_MQTT_PASSWORD",
                    "qos": 1,
                    "clean_start": True,
                    "session_expiry_seconds": 0,
                    "telemetry_message_expiry_seconds": 86400,
                    "connect_timeout_seconds": 5,
                    "retry_backoff_seconds": [5, 15, 60],
                },
            },
            "storage": {
                "sqlite_path": "/tmp/edge-telemetry-agent/outbox.db",
                "retention_days": 7,
                "dead_letter_after_attempts": 3,
            },
            "observability": {
                "log_level": "INFO",
                "emit_health_events": True,
                "metrics_bind": "0.0.0.0:9108",
            },
        },
        agent_runtime_data={
            "message_type": "idp.edge.agent-runtime-config.v1",
            "tenant_id": "tenant-001",
            "asset_id": "demo-stand-01",
            "agent_id": "edge-telemetry-agent-001",
            "config_revision": "rev-2026-05-02-001",
            "issued_at": "2026-05-02T00:00:00Z",
            "sources": [
                {
                    "source_id": "knx_main",
                    "source_config_revision": "rev-2026-05-02-001-knx-main",
                    "enabled": True,
                }
            ],
        },
        source_documents=[
            {
                "message_type": "idp.edge.source-config.v1",
                "tenant_id": "tenant-001",
                "asset_id": "demo-stand-01",
                "agent_id": "edge-telemetry-agent-001",
                "config_revision": "rev-2026-05-02-001",
                "source_id": "knx_main",
                "source_config_revision": "rev-2026-05-02-001-knx-main",
                "source_type": "knx",
                "enabled": True,
                "connection": {"gateway_ip": "127.0.0.1", "gateway_port": 3671},
                "acquisition_defaults": {
                    "listen": True,
                    "read_on_start": False,
                    "periodic_interval_seconds": None,
                },
                "publish_defaults": {
                    "enabled": True,
                    "change_threshold": None,
                },
                "points": [
                    {
                        "point_key": "0%2F0%2F7",
                        "point_ref": "0/0/7",
                        "name": "switch_feedback",
                        "value_type": "boolean",
                        "value_model": "knx.dpt.1.001",
                        "signal_type": "feedback",
                        "acquisition": {
                            "listen": True,
                            "read_on_start": False,
                            "periodic_interval_seconds": None,
                        },
                        "publish": {
                            "enabled": True,
                            "change_threshold": None,
                        },
                        "tags": {},
                    }
                ],
            }
        ],
    )


def _event_payload_json() -> str:
    event = TelemetryEvent.new(
        event_type="telemetry.changed",
        agent_id="edge-telemetry-agent-001",
        tenant_id="tenant-001",
        asset_id="demo-stand-01",
        source_id="knx_main",
        source_type="knx",
        source_config_revision="rev-2026-05-02-001-knx-main",
        point_ref="0/0/7",
        name="switch_feedback",
        description=None,
        value_type="boolean",
        value_model="knx.dpt.1.001",
        signal_type="feedback",
        observation_mode="listen",
        value=True,
        value_raw="01",
        quality="good",
        sequence=1,
        unit=None,
        tags={},
        ts=datetime(2026, 3, 28, 10, 0, tzinfo=UTC),
    )
    return json.dumps(event.canonical_payload())


def test_delivery_worker_publishes_outbox_telemetry_and_marks_sent() -> None:
    publisher = FakePublisher()
    outbox = FakeOutbox(
        [FakeOutboxRecord(record_id=7, payload_json=_event_payload_json(), attempt_count=1)]
    )
    worker = DeliveryWorker(
        runtime_config=_runtime_config(),
        agent_id="edge-telemetry-agent-001",
        outbox=outbox,
        publisher=publisher,
    )

    result = worker.deliver_once(now=datetime(2026, 3, 28, 10, 1, tzinfo=UTC))

    assert result.reserved_count == 1
    assert result.published_count == 1
    assert outbox.sent_ids == [7]
    assert publisher.publications[0].retain is False
    assert publisher.publications[0].message_expiry_seconds == 86400
    assert publisher.publications[0].topic == (
        "idp/v1/assets/demo-stand-01/agents/edge-telemetry-agent-001/sources/knx_main/points/0%2F0%2F7/event"
    )
    assert publisher.publications[0].payload["message_type"] == "idp.edge.telemetry.event.v1"
    assert publisher.publications[0].payload["tenant_id"] == "tenant-001"
    assert publisher.publications[0].payload["source_config_revision"] == (
        "rev-2026-05-02-001-knx-main"
    )


def test_delivery_worker_retries_failed_publish() -> None:
    outbox = FakeOutbox(
        [FakeOutboxRecord(record_id=7, payload_json=_event_payload_json(), attempt_count=1)]
    )
    worker = DeliveryWorker(
        runtime_config=_runtime_config(),
        agent_id="edge-telemetry-agent-001",
        outbox=outbox,
        publisher=FakePublisher(fail=True),
    )

    result = worker.deliver_once(now=datetime(2026, 3, 28, 10, 1, tzinfo=UTC))

    assert result.retry_count == 1
    assert outbox.retries == [
        (7, datetime(2026, 3, 28, 10, 1, 5, tzinfo=UTC), "publish failed")
    ]
    assert outbox.dead_letters == []


def test_delivery_worker_dead_letters_after_max_attempts() -> None:
    outbox = FakeOutbox(
        [FakeOutboxRecord(record_id=7, payload_json=_event_payload_json(), attempt_count=3)]
    )
    worker = DeliveryWorker(
        runtime_config=_runtime_config(),
        agent_id="edge-telemetry-agent-001",
        outbox=outbox,
        publisher=FakePublisher(fail=True),
    )

    result = worker.deliver_once(now=datetime(2026, 3, 28, 10, 1, tzinfo=UTC))

    assert result.dead_letter_count == 1
    assert outbox.dead_letters == [(7, "publish failed")]
