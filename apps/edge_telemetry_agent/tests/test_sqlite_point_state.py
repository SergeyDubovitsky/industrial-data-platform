from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from edge_telemetry_agent.application.processing import PointState
from edge_telemetry_agent.infrastructure.sqlite_point_state import SQLitePointStateCache


def test_sqlite_point_state_cache_round_trips_state(tmp_path) -> None:
    cache = SQLitePointStateCache(tmp_path / "state.db")
    cache.initialize()
    observed_at = datetime(2026, 5, 2, 8, 15, 30, tzinfo=UTC)
    published_at = datetime(2026, 5, 2, 8, 16, 45, tzinfo=UTC)

    cache.save(
        "knx_main",
        "2/0/0",
        PointState(
            last_observed_value=23.4,
            last_observed_at=observed_at,
            last_observed_raw="17.4",
            last_observed_quality="uncertain",
            last_published_value=23.0,
            last_published_at=published_at,
            last_published_raw="17.0",
            last_published_quality="good",
            published_count=7,
        ),
    )

    restored = cache.get("knx_main", "2/0/0")

    assert restored is not None
    assert restored.last_observed_value == 23.4
    assert restored.last_observed_at == observed_at
    assert restored.last_observed_raw == "17.4"
    assert restored.last_observed_quality == "uncertain"
    assert restored.last_published_value == 23.0
    assert restored.last_published_at == published_at
    assert restored.last_published_raw == "17.0"
    assert restored.last_published_quality == "good"
    assert restored.published_count == 7


def test_sqlite_point_state_cache_updates_existing_row(tmp_path) -> None:
    cache = SQLitePointStateCache(tmp_path / "state.db")
    cache.initialize()
    cache.save(
        "knx_main",
        "0/0/7",
        PointState(
            last_observed_value=False,
            last_published_value=False,
            published_count=1,
        ),
    )

    cache.save(
        "knx_main",
        "0/0/7",
        PointState(
            last_observed_value=True,
            last_published_value=True,
            published_count=2,
        ),
    )

    restored = cache.get("knx_main", "0/0/7")
    with sqlite3.connect(tmp_path / "state.db") as connection:
        row_count = connection.execute("SELECT COUNT(*) FROM point_state_cache").fetchone()[0]

    assert row_count == 1
    assert restored is not None
    assert restored.last_observed_value is True
    assert restored.last_published_value is True
    assert restored.published_count == 2


def test_sqlite_point_state_cache_returns_none_for_missing_point(tmp_path) -> None:
    cache = SQLitePointStateCache(tmp_path / "state.db")
    cache.initialize()

    assert cache.get("knx_main", "missing") is None


def test_sqlite_point_state_cache_migrates_legacy_minimal_table(tmp_path) -> None:
    db_path = tmp_path / "state.db"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE point_state_cache (
                source_id TEXT NOT NULL,
                point_ref TEXT NOT NULL,
                last_observed_value_json TEXT,
                last_published_value_json TEXT,
                sequence INTEGER NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (source_id, point_ref)
            )
            """
        )

    cache = SQLitePointStateCache(db_path)
    cache.initialize()
    cache.save(
        "knx_main",
        "0/0/1",
        PointState(
            last_observed_value=True,
            last_observed_raw="01",
            last_observed_quality="good",
            last_published_value=True,
            last_published_raw="01",
            last_published_quality="good",
            published_count=1,
        ),
    )

    restored = cache.get("knx_main", "0/0/1")

    assert restored is not None
    assert restored.last_observed_raw == "01"
    assert restored.last_published_quality == "good"
