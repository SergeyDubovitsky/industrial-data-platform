from __future__ import annotations

import json

import pytest

from edge_telemetry_agent.application.configuration import (
    build_agent_runtime_config,
    load_agent_runtime_config,
    load_bootstrap_config,
)
from edge_telemetry_agent.domain.config import ConfigurationError


def _bootstrap_data() -> dict[str, object]:
    return {
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
            "metrics_bind": "127.0.0.1:9108",
        },
    }


def _agent_runtime_payload() -> dict[str, object]:
    return {
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
    }


def _source_payload() -> dict[str, object]:
    return {
        "message_type": "idp.edge.source-config.v1",
        "tenant_id": "tenant-001",
        "asset_id": "demo-stand-01",
        "agent_id": "edge-telemetry-agent-001",
        "config_revision": "rev-2026-05-02-001",
        "source_id": "knx_main",
        "source_config_revision": "rev-2026-05-02-001-knx-main",
        "source_type": "knx",
        "enabled": True,
        "connection": {
            "gateway_ip": "192.0.2.177",
            "gateway_port": 3671,
        },
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
                "description": None,
                "value_type": "boolean",
                "value_model": "knx.dpt.1.001",
                "signal_type": "feedback",
                "unit": None,
                "acquisition": {
                    "listen": True,
                    "read_on_start": False,
                    "periodic_interval_seconds": None,
                },
                "publish": {
                    "enabled": True,
                    "change_threshold": None,
                },
                "tags": {"room": "demo"},
            },
            {
                "point_key": "2%2F0%2F0",
                "point_ref": "2/0/0",
                "name": "temperature",
                "description": "Room temperature",
                "value_type": "number",
                "value_model": "knx.dpt.9.001",
                "signal_type": "sensor",
                "unit": "C",
                "acquisition": {
                    "listen": True,
                    "read_on_start": True,
                    "periodic_interval_seconds": None,
                },
                "publish": {
                    "enabled": True,
                    "change_threshold": 1.0,
                },
                "tags": {"room": "demo", "equipment": "temp_1"},
            },
        ],
    }


def test_load_bootstrap_config_expands_env_placeholders(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MQTT_BROKER", "mqtt://localhost:1883")
    bootstrap_path = tmp_path / "bootstrap.yaml"
    bootstrap_path.write_text(
        """
agent_id: "edge-telemetry-agent-001"
delivery:
  transport: "mqtt"
  mqtt:
    enabled: true
    version: "5.0"
    broker: "${MQTT_BROKER}"
    topic_root: "idp/v1"
    client_id_prefix: "edge-telemetry-agent"
    username_env: "EDGE_AGENT_MQTT_USERNAME"
    password_env: "EDGE_AGENT_MQTT_PASSWORD"
    qos: 1
    clean_start: true
    session_expiry_seconds: 0
    telemetry_message_expiry_seconds: 60
    connect_timeout_seconds: 5
    retry_backoff_seconds: [1, 2, 5]
storage:
  sqlite_path: "/tmp/outbox.db"
  retention_days: 7
  dead_letter_after_attempts: 20
observability:
  log_level: "INFO"
  emit_health_events: true
  metrics_bind: "127.0.0.1:9108"
""".strip(),
        encoding="utf-8",
    )

    bootstrap = load_bootstrap_config(bootstrap_path)

    assert bootstrap.agent_id == "edge-telemetry-agent-001"
    assert bootstrap.delivery.mqtt is not None
    assert bootstrap.delivery.mqtt.broker == "mqtt://localhost:1883"


def test_build_agent_runtime_config_assembles_runtime() -> None:
    runtime = build_agent_runtime_config(
        bootstrap_data=_bootstrap_data(),
        agent_runtime_data=_agent_runtime_payload(),
        source_documents=[_source_payload()],
    )

    assert runtime.tenant_id == "tenant-001"
    assert runtime.asset_id == "demo-stand-01"
    assert runtime.agent_id == "edge-telemetry-agent-001"
    assert runtime.config_revision == "rev-2026-05-02-001"
    assert runtime.point("knx_main", "2/0/0").source_config_revision == (
        "rev-2026-05-02-001-knx-main"
    )
    assert runtime.point("knx_main", "2/0/0").publish.change_threshold == 1.0


def test_build_agent_runtime_config_rejects_agent_mismatch() -> None:
    agent_runtime_payload = _agent_runtime_payload()
    agent_runtime_payload["agent_id"] = "other-agent"

    with pytest.raises(ConfigurationError, match="agent_id"):
        build_agent_runtime_config(
            bootstrap_data=_bootstrap_data(),
            agent_runtime_data=agent_runtime_payload,
            source_documents=[_source_payload()],
        )


def test_build_agent_runtime_config_rejects_missing_source_config() -> None:
    with pytest.raises(ConfigurationError, match="Missing retained source config"):
        build_agent_runtime_config(
            bootstrap_data=_bootstrap_data(),
            agent_runtime_data=_agent_runtime_payload(),
            source_documents=[],
        )


def test_build_agent_runtime_config_rejects_source_revision_mismatch() -> None:
    source_payload = _source_payload()
    source_payload["source_config_revision"] = "rev-other"

    with pytest.raises(ConfigurationError, match="source_config_revision"):
        build_agent_runtime_config(
            bootstrap_data=_bootstrap_data(),
            agent_runtime_data=_agent_runtime_payload(),
            source_documents=[source_payload],
        )


def test_build_agent_runtime_config_rejects_threshold_for_boolean_point() -> None:
    source_payload = _source_payload()
    source_payload["points"][0]["publish"]["change_threshold"] = 0.5

    with pytest.raises(ConfigurationError, match="change_threshold"):
        build_agent_runtime_config(
            bootstrap_data=_bootstrap_data(),
            agent_runtime_data=_agent_runtime_payload(),
            source_documents=[source_payload],
        )


def test_load_agent_runtime_config_fetches_retained_documents(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bootstrap_path = tmp_path / "bootstrap.json"
    bootstrap_path.write_text(json.dumps(_bootstrap_data()), encoding="utf-8")

    class FakeLoader:
        def __init__(self, settings, *, agent_id: str) -> None:
            assert agent_id == "edge-telemetry-agent-001"

        def load(self):
            class Docs:
                agent_runtime_config = _agent_runtime_payload()
                source_configs = {"knx_main": _source_payload()}

            return Docs()

    monkeypatch.setattr("edge_telemetry_agent.application.configuration.RetainedConfigLoader", FakeLoader)

    runtime = load_agent_runtime_config(bootstrap_path)

    assert runtime.tenant_id == "tenant-001"
    assert sorted(runtime.sources) == ["knx_main"]
    assert runtime.point("knx_main", "0/0/7").name == "switch_feedback"


def test_load_bootstrap_config_rejects_invalid_agent_id(tmp_path) -> None:
    bootstrap_path = tmp_path / "bootstrap.json"
    payload = _bootstrap_data()
    payload["agent_id"] = "Edge Agent 001"
    bootstrap_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ConfigurationError, match="bootstrap config.agent_id"):
        load_bootstrap_config(bootstrap_path)


def test_load_bootstrap_config_rejects_invalid_topic_root(tmp_path) -> None:
    bootstrap_path = tmp_path / "bootstrap.json"
    payload = _bootstrap_data()
    payload["delivery"]["mqtt"]["topic_root"] = "idp/v1/+"
    bootstrap_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ConfigurationError, match="bootstrap config.delivery.mqtt.topic_root"):
        load_bootstrap_config(bootstrap_path)


def test_build_agent_runtime_config_rejects_invalid_asset_id() -> None:
    agent_runtime_payload = _agent_runtime_payload()
    agent_runtime_payload["asset_id"] = "Demo Stand 01"

    with pytest.raises(ConfigurationError, match="agent runtime config.asset_id"):
        build_agent_runtime_config(
            bootstrap_data=_bootstrap_data(),
            agent_runtime_data=agent_runtime_payload,
            source_documents=[_source_payload()],
        )


def test_build_agent_runtime_config_rejects_invalid_source_id() -> None:
    agent_runtime_payload = _agent_runtime_payload()
    agent_runtime_payload["sources"][0]["source_id"] = "knx/main"

    with pytest.raises(ConfigurationError, match="agent runtime config.sources.0.source_id"):
        build_agent_runtime_config(
            bootstrap_data=_bootstrap_data(),
            agent_runtime_data=agent_runtime_payload,
            source_documents=[_source_payload()],
        )


def test_build_agent_runtime_config_rejects_invalid_source_config_source_id() -> None:
    source_payload = _source_payload()
    source_payload["source_id"] = "knx main"

    with pytest.raises(ConfigurationError, match="source config #0.source_id"):
        build_agent_runtime_config(
            bootstrap_data=_bootstrap_data(),
            agent_runtime_data=_agent_runtime_payload(),
            source_documents=[source_payload],
        )
