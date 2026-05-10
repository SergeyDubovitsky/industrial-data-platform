from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from edge_telemetry_agent.application.configuration import build_agent_runtime_config
from edge_telemetry_agent.cli import main
from edge_telemetry_agent.domain.config import ConfigurationError


class FakePublisher:
    def __init__(self) -> None:
        self.publications: list[object] = []
        self.closed = False

    def publish(self, publication: object) -> None:
        self.publications.append(publication)

    def close(self) -> None:
        self.closed = True


def _runtime_config(tmp_path: Path):
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
                    "username_env": None,
                    "password_env": None,
                    "qos": 1,
                    "clean_start": True,
                    "session_expiry_seconds": 0,
                    "telemetry_message_expiry_seconds": 86400,
                    "connect_timeout_seconds": 5,
                    "retry_backoff_seconds": [5, 15, 60],
                },
            },
            "storage": {
                "sqlite_path": str(tmp_path / "state" / "outbox.db"),
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
                    "source_id": "demo_source",
                    "source_config_revision": "rev-2026-05-02-001-demo",
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
                "source_id": "demo_source",
                "source_config_revision": "rev-2026-05-02-001-demo",
                "source_type": "demo",
                "enabled": True,
                "connection": {},
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
                        "point_key": "command",
                        "point_ref": "command",
                        "name": "command",
                        "value_type": "boolean",
                        "value_model": "demo.boolean",
                        "signal_type": "command",
                        "acquisition": {
                            "listen": True,
                            "read_on_start": False,
                            "periodic_interval_seconds": None,
                        },
                        "publish": {
                            "enabled": False,
                            "change_threshold": None,
                        },
                        "tags": {},
                    },
                    {
                        "point_key": "temperature",
                        "point_ref": "temperature",
                        "name": "temperature",
                        "value_type": "number",
                        "value_model": "demo.number",
                        "signal_type": "sensor",
                        "unit": "C",
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


def test_check_config_command_uses_bootstrap_and_retained_runtime(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    runtime = _runtime_config(tmp_path)
    monkeypatch.setattr("edge_telemetry_agent.cli.load_agent_runtime_config", lambda path: runtime)

    exit_code = main(["check-config", "--bootstrap-config", str(tmp_path / "bootstrap.yaml")])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Configuration OK:" in captured.out
    assert "tenant_id=tenant-001" in captured.out
    assert "agent_id=edge-telemetry-agent-001" in captured.out


def test_show_config_json_outputs_summary(tmp_path, monkeypatch, capsys) -> None:
    runtime = _runtime_config(tmp_path)
    monkeypatch.setattr("edge_telemetry_agent.cli.load_agent_runtime_config", lambda path: runtime)

    exit_code = main(
        [
            "show-config",
            "--bootstrap-config",
            str(tmp_path / "bootstrap.yaml"),
            "--format",
            "json",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["tenant_id"] == "tenant-001"
    assert payload["source_count"] == 1
    assert payload["point_count"] == 2


def test_enqueue_demo_event_appends_publishable_event_to_sqlite_outbox(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    runtime = _runtime_config(tmp_path)
    monkeypatch.setattr("edge_telemetry_agent.cli.load_agent_runtime_config", lambda path: runtime)

    exit_code = main(
        [
            "enqueue-demo-event",
            "--bootstrap-config",
            str(tmp_path / "bootstrap.yaml"),
            "--source-id",
            "demo_source",
            "--point-ref",
            "temperature",
            "--value",
            "25.5",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Enqueued demo event:" in captured.out
    with sqlite3.connect(tmp_path / "state" / "outbox.db") as connection:
        row = connection.execute(
            "SELECT event_type, payload_json, status FROM outbox"
        ).fetchone()
    assert row[0] == "telemetry.sample"
    assert row[2] == "pending"
    payload = json.loads(row[1])
    assert payload["agent_id"] == "edge-telemetry-agent-001"
    assert payload["tenant_id"] == "tenant-001"
    assert payload["source_config_revision"] == "rev-2026-05-02-001-demo"
    assert payload["value"] == 25.5
    with sqlite3.connect(tmp_path / "state" / "outbox.db") as connection:
        state_row = connection.execute(
            """
            SELECT
                last_observed_value_json,
                last_observed_raw,
                last_observed_quality,
                last_published_value_json,
                last_published_raw,
                last_published_quality,
                sequence
            FROM point_state_cache
            WHERE source_id = 'demo_source' AND point_ref = 'temperature'
            """
        ).fetchone()
    assert state_row == ("25.5", "25.5", "good", "25.5", "25.5", "good", 1)


def test_deliver_once_publishes_pending_outbox_event_and_marks_sent(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    runtime = _runtime_config(tmp_path)
    fake_publisher = FakePublisher()
    monkeypatch.setattr("edge_telemetry_agent.cli.load_agent_runtime_config", lambda path: runtime)
    monkeypatch.setattr(
        "edge_telemetry_agent.cli.connect_mqtt_publisher",
        lambda settings, *, agent_id: fake_publisher,
    )
    assert (
        main(
            [
                "enqueue-demo-event",
                "--bootstrap-config",
                str(tmp_path / "bootstrap.yaml"),
                "--source-id",
                "demo_source",
                "--point-ref",
                "temperature",
            ]
        )
        == 0
    )
    capsys.readouterr()

    exit_code = main(
        [
            "deliver-once",
            "--bootstrap-config",
            str(tmp_path / "bootstrap.yaml"),
            "--limit",
            "10",
            "--lease-seconds",
            "30",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Delivery run: reserved=1 published=1 retry=0 dead_letter=0" in captured.out
    assert len(fake_publisher.publications) == 1
    publication = fake_publisher.publications[0]
    assert publication.topic == (
        "idp/v1/assets/demo-stand-01/agents/edge-telemetry-agent-001"
        "/sources/demo_source/points/temperature/event"
    )
    assert publication.payload["tenant_id"] == "tenant-001"
    assert publication.payload["source_config_revision"] == "rev-2026-05-02-001-demo"
    assert fake_publisher.closed is True
    with sqlite3.connect(tmp_path / "state" / "outbox.db") as connection:
        status = connection.execute("SELECT status FROM outbox").fetchone()[0]
    assert status == "sent"


def test_check_config_command_returns_error_for_invalid_runtime(monkeypatch, capsys) -> None:
    def fail(_path: Path):
        raise ConfigurationError("broken runtime")

    monkeypatch.setattr("edge_telemetry_agent.cli.load_agent_runtime_config", fail)

    exit_code = main(["check-config", "--bootstrap-config", "/tmp/bootstrap.yaml"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "ERROR: broken runtime" in captured.err
