from __future__ import annotations

from datetime import UTC, datetime

from idp_telemetry_store.load_poc import (
    TelemetryReadModelLoadPocConfig,
    run_telemetry_read_model_load_poc,
)


class FakeClickHouseClient:
    def __init__(self) -> None:
        self.sql: list[str] = []

    def execute(self, sql: str) -> str:
        self.sql.append(sql)
        if "FROM telemetry_events_dedup_v1" in sql and "point_key = 'point-00000'" in sql:
            return "3\t20.0\n"
        if "FROM telemetry_events_dedup_v1" in sql:
            return "5\n"
        if "FROM telemetry_latest_v1" in sql:
            return "2\n"
        if "FROM telemetry_1m_v1" in sql:
            return "5\t5\n"
        if "FROM telemetry_1h_v1" in sql:
            return "1\t5\n"
        return ""


def test_load_poc_batches_rows_and_reports_read_model_metrics() -> None:
    client = FakeClickHouseClient()

    result = run_telemetry_read_model_load_poc(
        client,
        TelemetryReadModelLoadPocConfig(
            rows=5,
            points=2,
            batch_size=3,
            duplicate_every=2,
            run_id="unit",
            start_ts=datetime(2026, 5, 3, tzinfo=UTC),
        ),
    )

    insert_statements = [
        sql for sql in client.sql if sql.startswith("INSERT INTO telemetry_events_v1")
    ]
    inserted_lines = [
        line
        for statement in insert_statements
        for line in statement.splitlines()
        if line.startswith("poc-tenant-unit")
    ]

    assert result["logical_rows"] == 5
    assert result["duplicate_rows"] == 2
    assert result["inserted_rows"] == 7
    assert len(insert_statements) == 3
    assert len(inserted_lines) == 7
    assert result["queries"]["dedup_count"]["value"] == 5
    assert result["queries"]["latest_count"]["value"] == 2
