from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from edge_telemetry_agent.application.processing import PointState


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _to_optional_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).isoformat()


def _from_optional_iso(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value)


def _to_json(value: object | None) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def _from_json(value: str | None) -> object | None:
    if value is None:
        return None
    return json.loads(value)


class SQLitePointStateCache:
    def __init__(self, sqlite_path: Path) -> None:
        self._sqlite_path = sqlite_path

    def initialize(self) -> None:
        self._sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS point_state_cache (
                    source_id TEXT NOT NULL,
                    point_ref TEXT NOT NULL,
                    last_observed_at TEXT,
                    last_observed_value_json TEXT,
                    last_observed_raw TEXT,
                    last_observed_quality TEXT,
                    last_published_at TEXT,
                    last_published_value_json TEXT,
                    last_published_raw TEXT,
                    last_published_quality TEXT,
                    sequence INTEGER NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (source_id, point_ref)
                )
                """
            )
            _ensure_columns(
                connection,
                "point_state_cache",
                {
                    "last_observed_at": "TEXT",
                    "last_observed_raw": "TEXT",
                    "last_observed_quality": "TEXT",
                    "last_published_at": "TEXT",
                    "last_published_raw": "TEXT",
                    "last_published_quality": "TEXT",
                },
            )

    def get(self, source_id: str, point_ref: str) -> PointState | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    last_observed_at,
                    last_observed_value_json,
                    last_observed_raw,
                    last_observed_quality,
                    last_published_at,
                    last_published_value_json,
                    last_published_raw,
                    last_published_quality,
                    sequence
                FROM point_state_cache
                WHERE source_id = ? AND point_ref = ?
                """,
                (source_id, point_ref),
            ).fetchone()
        if row is None:
            return None
        return PointState(
            last_observed_value=_from_json(row["last_observed_value_json"]),
            last_observed_at=_from_optional_iso(row["last_observed_at"]),
            last_observed_raw=row["last_observed_raw"],
            last_observed_quality=row["last_observed_quality"],
            last_published_value=_from_json(row["last_published_value_json"]),
            last_published_at=_from_optional_iso(row["last_published_at"]),
            last_published_raw=row["last_published_raw"],
            last_published_quality=row["last_published_quality"],
            published_count=int(row["sequence"]),
        )

    def save(self, source_id: str, point_ref: str, state: PointState) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO point_state_cache (
                    source_id,
                    point_ref,
                    last_observed_at,
                    last_observed_value_json,
                    last_observed_raw,
                    last_observed_quality,
                    last_published_at,
                    last_published_value_json,
                    last_published_raw,
                    last_published_quality,
                    sequence,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id, point_ref) DO UPDATE SET
                    last_observed_at = excluded.last_observed_at,
                    last_observed_value_json = excluded.last_observed_value_json,
                    last_observed_raw = excluded.last_observed_raw,
                    last_observed_quality = excluded.last_observed_quality,
                    last_published_at = excluded.last_published_at,
                    last_published_value_json = excluded.last_published_value_json,
                    last_published_raw = excluded.last_published_raw,
                    last_published_quality = excluded.last_published_quality,
                    sequence = excluded.sequence,
                    updated_at = excluded.updated_at
                """,
                (
                    source_id,
                    point_ref,
                    _to_optional_iso(state.last_observed_at),
                    _to_json(state.last_observed_value),
                    state.last_observed_raw,
                    state.last_observed_quality,
                    _to_optional_iso(state.last_published_at),
                    _to_json(state.last_published_value),
                    state.last_published_raw,
                    state.last_published_quality,
                    state.published_count,
                    _now_iso(),
                ),
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._sqlite_path)
        connection.row_factory = sqlite3.Row
        return connection


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
