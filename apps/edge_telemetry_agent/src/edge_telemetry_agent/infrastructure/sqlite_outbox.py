from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from edge_telemetry_agent.domain.events import TelemetryEvent
from edge_telemetry_agent.modeling import FrozenEdgeModel


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _to_iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def _from_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _from_optional_iso(value: str | None) -> datetime | None:
    if value is None:
        return None
    return _from_iso(value)


class OutboxRecord(FrozenEdgeModel):
    id: int
    event_id: str
    event_type: str
    payload_json: str
    status: str
    created_at: datetime
    available_at: datetime
    reserved_at: datetime | None
    lease_expires_at: datetime | None
    sent_at: datetime | None
    attempt_count: int
    last_error: str | None


class SQLiteOutbox:
    def __init__(self, sqlite_path: Path) -> None:
        self._sqlite_path = sqlite_path

    def initialize(self) -> None:
        self._sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS outbox (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    available_at TEXT NOT NULL,
                    reserved_at TEXT,
                    lease_expires_at TEXT,
                    sent_at TEXT,
                    attempt_count INTEGER NOT NULL,
                    last_error TEXT
                )
                """
            )
            _ensure_columns(
                connection,
                "outbox",
                {
                    "reserved_at": "TEXT",
                    "lease_expires_at": "TEXT",
                    "sent_at": "TEXT",
                },
            )

    def append(
        self, event: TelemetryEvent, available_at: datetime | None = None
    ) -> int:
        now = _now()
        ready_at = available_at or now
        payload_json = json.dumps(
            event.canonical_payload(),
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO outbox (
                    event_id,
                    event_type,
                    payload_json,
                    status,
                    created_at,
                    available_at,
                    reserved_at,
                    lease_expires_at,
                    sent_at,
                    attempt_count,
                    last_error
                ) VALUES (?, ?, ?, 'pending', ?, ?, NULL, NULL, NULL, 0, NULL)
                """,
                (
                    event.event_id,
                    event.event_type,
                    payload_json,
                    _to_iso(now),
                    _to_iso(ready_at),
                ),
            )
            record_id = cursor.lastrowid
        if record_id is None:
            raise RuntimeError("Failed to append event to outbox")
        return int(record_id)

    def list_available(
        self, *, limit: int = 100, now: datetime | None = None
    ) -> list[OutboxRecord]:
        ready_at = _to_iso(now or _now())
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    id,
                    event_id,
                    event_type,
                    payload_json,
                    status,
                    created_at,
                    available_at,
                    reserved_at,
                    lease_expires_at,
                    sent_at,
                    attempt_count,
                    last_error
                FROM outbox
                WHERE status = 'pending' AND available_at <= ?
                ORDER BY id ASC
                LIMIT ?
                """,
                (ready_at, limit),
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def reserve_batch(
        self,
        *,
        limit: int = 100,
        now: datetime | None = None,
        lease_seconds: int = 60,
    ) -> list[OutboxRecord]:
        timestamp = now or _now()
        ready_at = _to_iso(timestamp)
        lease_expires_at = _to_iso(timestamp + timedelta(seconds=lease_seconds))
        with self._connect() as connection:
            _recover_expired_inflight(connection, now=ready_at)
            rows = connection.execute(
                """
                SELECT
                    id,
                    event_id,
                    event_type,
                    payload_json,
                    status,
                    created_at,
                    available_at,
                    reserved_at,
                    lease_expires_at,
                    sent_at,
                    attempt_count,
                    last_error
                FROM outbox
                WHERE status = 'pending' AND available_at <= ?
                ORDER BY id ASC
                LIMIT ?
                """,
                (ready_at, limit),
            ).fetchall()
            if not rows:
                return []
            record_ids = [row[0] for row in rows]
            connection.executemany(
                """
                UPDATE outbox
                SET
                    status = 'inflight',
                    attempt_count = attempt_count + 1,
                    reserved_at = ?,
                    lease_expires_at = ?
                WHERE id = ?
                """,
                ((ready_at, lease_expires_at, record_id) for record_id in record_ids),
            )
            refreshed_rows = connection.execute(
                f"""
                SELECT
                    id,
                    event_id,
                    event_type,
                    payload_json,
                    status,
                    created_at,
                    available_at,
                    reserved_at,
                    lease_expires_at,
                    sent_at,
                    attempt_count,
                    last_error
                FROM outbox
                WHERE id IN ({",".join("?" for _ in record_ids)})
                ORDER BY id ASC
                """,
                record_ids,
            ).fetchall()
        return [self._row_to_record(row) for row in refreshed_rows]

    def recover_expired_inflight(self, *, now: datetime | None = None) -> int:
        ready_at = _to_iso(now or _now())
        with self._connect() as connection:
            return _recover_expired_inflight(connection, now=ready_at)

    def mark_sent(self, record_id: int) -> None:
        sent_at = _to_iso(_now())
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE outbox
                SET
                    status = 'sent',
                    sent_at = ?,
                    reserved_at = NULL,
                    lease_expires_at = NULL,
                    last_error = NULL
                WHERE id = ?
                """,
                (sent_at, record_id),
            )

    def mark_retry(self, record_id: int, *, retry_at: datetime, error: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE outbox
                SET
                    status = 'pending',
                    available_at = ?,
                    reserved_at = NULL,
                    lease_expires_at = NULL,
                    last_error = ?
                WHERE id = ?
                """,
                (_to_iso(retry_at), error, record_id),
            )

    def mark_dead_letter(self, record_id: int, *, error: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE outbox
                SET
                    status = 'dead_letter',
                    reserved_at = NULL,
                    lease_expires_at = NULL,
                    last_error = ?
                WHERE id = ?
                """,
                (error, record_id),
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._sqlite_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _row_to_record(self, row: sqlite3.Row) -> OutboxRecord:
        return OutboxRecord(
            id=int(row["id"]),
            event_id=str(row["event_id"]),
            event_type=str(row["event_type"]),
            payload_json=str(row["payload_json"]),
            status=str(row["status"]),
            created_at=_from_iso(str(row["created_at"])),
            available_at=_from_iso(str(row["available_at"])),
            reserved_at=_from_optional_iso(row["reserved_at"]),
            lease_expires_at=_from_optional_iso(row["lease_expires_at"]),
            sent_at=_from_optional_iso(row["sent_at"]),
            attempt_count=int(row["attempt_count"]),
            last_error=row["last_error"],
        )


def _ensure_columns(
    connection: sqlite3.Connection,
    table_name: str,
    columns: dict[str, str],
) -> None:
    existing = {
        str(row["name"])
        for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    for column_name, column_type in columns.items():
        if column_name not in existing:
            connection.execute(
                f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
            )


def _recover_expired_inflight(connection: sqlite3.Connection, *, now: str) -> int:
    cursor = connection.execute(
        """
        UPDATE outbox
        SET
            status = 'pending',
            available_at = ?,
            reserved_at = NULL,
            lease_expires_at = NULL,
            last_error = COALESCE(last_error, 'lease_expired')
        WHERE status = 'inflight'
          AND lease_expires_at IS NOT NULL
          AND lease_expires_at <= ?
        """,
        (now, now),
    )
    return cursor.rowcount
