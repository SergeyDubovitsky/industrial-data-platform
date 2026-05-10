from __future__ import annotations

from datetime import UTC, datetime

from edge_telemetry_agent.application.configuration import build_agent_runtime_config
from edge_telemetry_agent.application.processing import ObservationProcessor
from edge_telemetry_agent.domain.events import Observation
from edge_telemetry_agent.infrastructure.mqtt_contracts import (
    telemetry_payload_from_event,
    telemetry_topic,
)
from edge_telemetry_agent.infrastructure.sqlite_point_state import SQLitePointStateCache


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
                "dead_letter_after_attempts": 20,
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
                    },
                    {
                        "point_key": "2%2F0%2F0",
                        "point_ref": "2/0/0",
                        "name": "temperature",
                        "value_type": "number",
                        "value_model": "knx.dpt.9.001",
                        "signal_type": "sensor",
                        "unit": "C",
                        "acquisition": {
                            "listen": True,
                            "read_on_start": False,
                            "periodic_interval_seconds": None,
                        },
                        "publish": {
                            "enabled": True,
                            "change_threshold": 1.0,
                        },
                        "tags": {},
                    },
                    {
                        "point_key": "0%2F0%2F1",
                        "point_ref": "0/0/1",
                        "name": "switch_command",
                        "value_type": "boolean",
                        "value_model": "knx.dpt.1.001",
                        "signal_type": "command",
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
                    },
                ],
            }
        ],
    )


def test_processing_emits_boolean_event_and_suppresses_duplicate() -> None:
    runtime = _runtime_config()
    processor = ObservationProcessor(runtime, agent_id="edge-telemetry-agent-001")
    ts = datetime(2026, 3, 28, 10, 0, tzinfo=UTC)

    first = processor.process(
        Observation(
            source_id="knx_main",
            point_ref="0/0/7",
            observation_mode="listen",
            value=True,
            value_raw="01",
            observed_at=ts,
        )
    )
    second = processor.process(
        Observation(
            source_id="knx_main",
            point_ref="0/0/7",
            observation_mode="listen",
            value=True,
            value_raw="01",
            observed_at=ts,
        )
    )

    assert first.event is not None
    assert first.event.event_type == "telemetry.changed"
    assert first.event.sequence == 1
    assert first.event.tenant_id == "tenant-001"
    assert first.event.source_config_revision == "rev-2026-05-02-001-knx-main"
    assert telemetry_payload_from_event(first.event) == {
        "message_type": "idp.edge.telemetry.event.v1",
        "tenant_id": "tenant-001",
        "event_id": first.event.event_id,
        "event_type": "telemetry.changed",
        "source_config_revision": "rev-2026-05-02-001-knx-main",
        "ts": "2026-03-28T10:00:00Z",
        "observation_mode": "listen",
        "value": True,
        "value_raw": "01",
        "quality": "good",
        "sequence": 1,
    }
    assert (
        telemetry_topic(
            topic_root="idp/v1",
            asset_id=first.event.asset_id,
            agent_id=first.event.agent_id,
            source_id=first.event.source_id,
            point_ref=first.event.point_ref,
        )
        == "idp/v1/assets/demo-stand-01/agents/edge-telemetry-agent-001/sources/knx_main/points/0%2F0%2F7/event"
    )
    assert second.event is None
    assert second.suppressed_reason == "not_significant"


def test_processing_uses_threshold_for_numeric_points() -> None:
    runtime = _runtime_config()
    processor = ObservationProcessor(runtime, agent_id="edge-telemetry-agent-001")
    ts = datetime(2026, 3, 28, 10, 0, tzinfo=UTC)

    first = processor.process(
        Observation(
            source_id="knx_main",
            point_ref="2/0/0",
            observation_mode="read_on_start",
            value=23.0,
            observed_at=ts,
        )
    )
    second = processor.process(
        Observation(
            source_id="knx_main",
            point_ref="2/0/0",
            observation_mode="listen",
            value=23.4,
            observed_at=ts,
        )
    )
    third = processor.process(
        Observation(
            source_id="knx_main",
            point_ref="2/0/0",
            observation_mode="listen",
            value=24.0,
            observed_at=ts,
        )
    )

    assert first.event is not None
    assert first.event.event_type == "telemetry.sample"
    assert second.event is None
    assert second.suppressed_reason == "not_significant"
    assert third.event is not None
    assert third.event.sequence == 2


def test_processing_suppresses_command_point_even_when_publish_enabled() -> None:
    runtime = _runtime_config()
    processor = ObservationProcessor(runtime, agent_id="edge-telemetry-agent-001")

    result = processor.process(
        Observation(
            source_id="knx_main",
            point_ref="0/0/1",
            observation_mode="listen",
            value=True,
        )
    )

    assert result.event is None
    assert result.suppressed_reason == "command_point"


def test_processing_restores_published_state_after_restart(tmp_path) -> None:
    runtime = _runtime_config()
    state_cache = SQLitePointStateCache(tmp_path / "state.db")
    state_cache.initialize()
    ts = datetime(2026, 3, 28, 10, 0, tzinfo=UTC)

    first_processor = ObservationProcessor(
        runtime,
        agent_id="edge-telemetry-agent-001",
        state_store=state_cache,
    )
    first = first_processor.process(
        Observation(
            source_id="knx_main",
            point_ref="2/0/0",
            observation_mode="listen",
            value=23.0,
            observed_at=ts,
        )
    )

    restarted_processor = ObservationProcessor(
        runtime,
        agent_id="edge-telemetry-agent-001",
        state_store=state_cache,
    )
    suppressed = restarted_processor.process(
        Observation(
            source_id="knx_main",
            point_ref="2/0/0",
            observation_mode="listen",
            value=23.4,
            observed_at=ts,
        )
    )
    changed = restarted_processor.process(
        Observation(
            source_id="knx_main",
            point_ref="2/0/0",
            observation_mode="listen",
            value=24.0,
            observed_at=ts,
        )
    )

    assert first.event is not None
    assert first.event.sequence == 1
    assert suppressed.event is None
    assert suppressed.suppressed_reason == "not_significant"
    assert changed.event is not None
    assert changed.event.sequence == 2
