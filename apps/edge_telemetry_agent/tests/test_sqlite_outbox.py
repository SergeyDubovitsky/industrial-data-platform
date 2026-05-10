from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from edge_telemetry_agent.domain.events import TelemetryEvent
from edge_telemetry_agent.infrastructure.sqlite_outbox import SQLiteOutbox


def _event() -> TelemetryEvent:
    return TelemetryEvent.new(
        event_type="telemetry.changed",
        agent_id="edge-telemetry-agent-001",
        tenant_id="tenant-001",
        asset_id="demo-stand-01",
        source_id="knx_main",
        source_type="knx",
        source_config_revision="rev-2026-05-02-001-knx-main",
        point_ref="0/0/7",
        name="switch_feedback",
        description="Feedback",
        value_type="boolean",
        value_model="knx.dpt.1.001",
        signal_type="feedback",
        observation_mode="listen",
        value=True,
        value_raw="01",
        quality="good",
        sequence=1,
        unit=None,
        tags={"room": "demo"},
        ts=datetime(2026, 3, 28, 10, 0, tzinfo=UTC),
    )


def test_sqlite_outbox_append_reserve_retry_and_send(tmp_path) -> None:
    outbox = SQLiteOutbox(Path(tmp_path / "outbox.db"))
    outbox.initialize()
    record_id = outbox.append(
        _event(),
        available_at=datetime(2026, 3, 28, 10, 0, tzinfo=UTC),
    )

    available = outbox.list_available(now=datetime(2026, 3, 28, 10, 1, tzinfo=UTC))
    assert [record.id for record in available] == [record_id]

    reserve_time = datetime(2026, 3, 28, 10, 1, tzinfo=UTC)
    reserved = outbox.reserve_batch(now=reserve_time, lease_seconds=30)
    assert len(reserved) == 1
    assert reserved[0].status == "inflight"
    assert reserved[0].attempt_count == 1
    assert reserved[0].reserved_at == reserve_time
    assert reserved[0].lease_expires_at == reserve_time + timedelta(seconds=30)

    retry_at = datetime(2026, 3, 28, 10, 5, tzinfo=UTC)
    outbox.mark_retry(record_id, retry_at=retry_at, error="timeout")

    not_ready = outbox.list_available(now=retry_at - timedelta(seconds=1))
    assert not not_ready

    ready_again = outbox.list_available(now=retry_at)
    assert [record.id for record in ready_again] == [record_id]
    assert ready_again[0].last_error == "timeout"
    assert ready_again[0].reserved_at is None
    assert ready_again[0].lease_expires_at is None

    outbox.mark_sent(record_id)
    assert not outbox.list_available(now=retry_at + timedelta(seconds=1))


def test_sqlite_outbox_marks_dead_letter(tmp_path) -> None:
    outbox = SQLiteOutbox(Path(tmp_path / "outbox.db"))
    outbox.initialize()
    record_id = outbox.append(_event())

    outbox.mark_dead_letter(record_id, error="too-many-attempts")

    assert not outbox.list_available(now=datetime(2026, 3, 28, 10, 1, tzinfo=UTC))


def test_sqlite_outbox_recovers_expired_inflight_records(tmp_path) -> None:
    outbox = SQLiteOutbox(Path(tmp_path / "outbox.db"))
    outbox.initialize()
    record_id = outbox.append(
        _event(),
        available_at=datetime(2026, 3, 28, 10, 0, tzinfo=UTC),
    )

    reserved = outbox.reserve_batch(
        now=datetime(2026, 3, 28, 10, 1, tzinfo=UTC),
        lease_seconds=30,
    )
    assert [record.id for record in reserved] == [record_id]

    recovered_count = outbox.recover_expired_inflight(
        now=datetime(2026, 3, 28, 10, 2, tzinfo=UTC)
    )

    assert recovered_count == 1
    ready_again = outbox.list_available(now=datetime(2026, 3, 28, 10, 2, tzinfo=UTC))
    assert [record.id for record in ready_again] == [record_id]
    assert ready_again[0].last_error == "lease_expired"


def test_sqlite_outbox_migrates_legacy_table(tmp_path) -> None:
    sqlite_path = Path(tmp_path / "outbox.db")
    with sqlite3.connect(sqlite_path) as connection:
        connection.execute(
            """
            CREATE TABLE outbox (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL UNIQUE,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                available_at TEXT NOT NULL,
                attempt_count INTEGER NOT NULL,
                last_error TEXT
            )
            """
        )

    outbox = SQLiteOutbox(sqlite_path)
    outbox.initialize()
    record_id = outbox.append(
        _event(),
        available_at=datetime(2026, 3, 28, 10, 0, tzinfo=UTC),
    )

    reserved = outbox.reserve_batch(now=datetime(2026, 3, 28, 10, 1, tzinfo=UTC))

    assert [record.id for record in reserved] == [record_id]
    assert reserved[0].reserved_at == datetime(2026, 3, 28, 10, 1, tzinfo=UTC)
