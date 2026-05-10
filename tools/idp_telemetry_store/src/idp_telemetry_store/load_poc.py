from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol


class ClickHouseClient(Protocol):
    def execute(self, sql: str) -> str:
        """Execute SQL and return ClickHouse response text."""


@dataclass(frozen=True)
class TelemetryReadModelLoadPocConfig:
    rows: int = 50_000
    points: int = 100
    batch_size: int = 10_000
    duplicate_every: int = 10
    run_id: str | None = None
    start_ts: datetime | None = None


def run_telemetry_read_model_load_poc(
    client: ClickHouseClient,
    config: TelemetryReadModelLoadPocConfig,
) -> dict[str, object]:
    _validate_config(config)
    run_id = config.run_id or datetime.now(tz=UTC).strftime("%Y%m%d%H%M%S")
    start_ts = config.start_ts or datetime(2026, 5, 3, tzinfo=UTC)
    tenant_id = f"poc-tenant-{run_id}"
    asset_id = f"poc-asset-{run_id}"
    source_id = "poc-source"

    insert_started = time.perf_counter()
    inserted_rows = 0
    duplicate_rows = 0
    batch: list[str] = []

    for row_index in range(config.rows):
        batch.append(
            _telemetry_row_tsv(
                run_id=run_id,
                tenant_id=tenant_id,
                asset_id=asset_id,
                source_id=source_id,
                row_index=row_index,
                point_index=row_index % config.points,
                total_points=config.points,
                ts=start_ts + timedelta(seconds=row_index),
                duplicate=False,
            )
        )
        inserted_rows += 1

        if config.duplicate_every > 0 and (row_index + 1) % config.duplicate_every == 0:
            batch.append(
                _telemetry_row_tsv(
                    run_id=run_id,
                    tenant_id=tenant_id,
                    asset_id=asset_id,
                    source_id=source_id,
                    row_index=row_index,
                    point_index=row_index % config.points,
                    total_points=config.points,
                    ts=start_ts + timedelta(seconds=row_index),
                    duplicate=True,
                )
            )
            inserted_rows += 1
            duplicate_rows += 1

        if len(batch) >= config.batch_size:
            _insert_batch(client, batch)
            batch = []

    if batch:
        _insert_batch(client, batch)

    insert_seconds = time.perf_counter() - insert_started
    queries = _measure_read_model_queries(
        client,
        tenant_id=tenant_id,
        asset_id=asset_id,
        source_id=source_id,
    )

    return {
        "run_id": run_id,
        "tenant_id": tenant_id,
        "asset_id": asset_id,
        "source_id": source_id,
        "logical_rows": config.rows,
        "duplicate_rows": duplicate_rows,
        "inserted_rows": inserted_rows,
        "points": config.points,
        "batch_size": config.batch_size,
        "insert_seconds": round(insert_seconds, 6),
        "rows_per_second": round(inserted_rows / insert_seconds, 2)
        if insert_seconds > 0
        else None,
        "queries": queries,
    }


def result_to_json(result: dict[str, object]) -> str:
    return json.dumps(result, indent=2, sort_keys=True)


def _validate_config(config: TelemetryReadModelLoadPocConfig) -> None:
    if config.rows <= 0:
        raise ValueError("rows must be greater than zero")
    if config.points <= 0:
        raise ValueError("points must be greater than zero")
    if config.batch_size <= 0:
        raise ValueError("batch_size must be greater than zero")
    if config.duplicate_every < 0:
        raise ValueError("duplicate_every must be greater than or equal to zero")


def _insert_batch(client: ClickHouseClient, rows: list[str]) -> None:
    client.execute(
        "\n".join(
            (
                "INSERT INTO telemetry_events_v1",
                "FORMAT TabSeparated",
                *rows,
            )
        )
    )


def _telemetry_row_tsv(
    *,
    run_id: str,
    tenant_id: str,
    asset_id: str,
    source_id: str,
    row_index: int,
    point_index: int,
    total_points: int,
    ts: datetime,
    duplicate: bool,
) -> str:
    point_key = f"point-{point_index:05d}"
    event_id = f"{run_id}-{row_index:08d}"
    value = round((row_index % 10_000) / 10, 2)
    ingested_at = ts + timedelta(milliseconds=2 if duplicate else 1)
    quality = "bad" if row_index % 50 == 0 else "uncertain" if row_index % 20 == 0 else "good"

    values = [
        tenant_id,
        event_id,
        f"{tenant_id}|{asset_id}|poc-agent|{event_id}",
        asset_id,
        "poc-agent",
        source_id,
        "poc",
        f"{tenant_id}|{asset_id}|{source_id}|{point_key}",
        point_key,
        point_key,
        "poc-source-config-revision",
        _format_clickhouse_datetime64(ts),
        _format_clickhouse_datetime64(ingested_at),
        "telemetry.sample",
        "periodic_read",
        "number",
        str(value),
        r"\N",
        r"\N",
        str(value),
        quality,
        str((row_index // total_points) + 1),
    ]
    return "\t".join(values)


def _measure_read_model_queries(
    client: ClickHouseClient,
    *,
    tenant_id: str,
    asset_id: str,
    source_id: str,
) -> dict[str, object]:
    return {
        "dedup_count": _timed_scalar_query(
            client,
            f"""
            SELECT count()
            FROM telemetry_events_dedup_v1
            WHERE tenant_id = {_sql_string(tenant_id)}
              AND asset_id = {_sql_string(asset_id)}
            FORMAT TabSeparatedRaw
            """.strip(),
            parser=int,
        ),
        "latest_count": _timed_scalar_query(
            client,
            f"""
            SELECT count()
            FROM telemetry_latest_v1
            WHERE tenant_id = {_sql_string(tenant_id)}
              AND asset_id = {_sql_string(asset_id)}
            FORMAT TabSeparatedRaw
            """.strip(),
            parser=int,
        ),
        "minute_rollup": _timed_rollup_query(
            client,
            grain="1m",
            query=f"""
            SELECT count(), sum(event_count)
            FROM telemetry_1m_v1
            WHERE tenant_id = {_sql_string(tenant_id)}
              AND asset_id = {_sql_string(asset_id)}
            FORMAT TabSeparatedRaw
            """.strip(),
        ),
        "hour_rollup": _timed_rollup_query(
            client,
            grain="1h",
            query=f"""
            SELECT count(), sum(event_count)
            FROM telemetry_1h_v1
            WHERE tenant_id = {_sql_string(tenant_id)}
              AND asset_id = {_sql_string(asset_id)}
            FORMAT TabSeparatedRaw
            """.strip(),
        ),
        "one_point_history": _timed_rollup_query(
            client,
            grain="point",
            query=f"""
            SELECT count(), avg(value_float)
            FROM telemetry_events_dedup_v1
            WHERE tenant_id = {_sql_string(tenant_id)}
              AND asset_id = {_sql_string(asset_id)}
              AND source_id = {_sql_string(source_id)}
              AND point_key = 'point-00000'
            FORMAT TabSeparatedRaw
            """.strip(),
        ),
    }


def _timed_scalar_query(
    client: ClickHouseClient,
    query: str,
    *,
    parser: type[int],
) -> dict[str, object]:
    started = time.perf_counter()
    raw = client.execute(query).strip()
    return {
        "seconds": round(time.perf_counter() - started, 6),
        "value": parser(raw),
    }


def _timed_rollup_query(
    client: ClickHouseClient,
    *,
    grain: str,
    query: str,
) -> dict[str, object]:
    started = time.perf_counter()
    raw = client.execute(query).strip()
    first, _, second = raw.partition("\t")
    return {
        "grain": grain,
        "seconds": round(time.perf_counter() - started, 6),
        "rows": int(first),
        "value": float(second) if "." in second else int(second),
    }


def _format_clickhouse_datetime64(value: datetime) -> str:
    normalized = value.astimezone(UTC)
    return normalized.strftime("%Y-%m-%d %H:%M:%S.%f")[:23]


def _sql_string(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"
