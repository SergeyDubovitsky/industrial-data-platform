# ClickHouse Analytics Readiness

Дата: 2026-05-03
Статус: working draft

## Workload Summary

- workload: IoT / telemetry
- latency target: local MVP smoke first; future UI/API reads should be
  interactive for latest state and bounded time-range charts
- data shape: append-heavy telemetry events with at-least-once delivery and
  replay duplicates
- primary query patterns: latest value by point, point history by
  tenant/asset/source/point/time range, minute/hour rollups for charts
- operational constraints: Kafka Connect writes raw landing tables;
  ClickHouse owns contract validation and read models

## Rules Checked

- Per `schema-pk-plan-before-creation`: ORDER BY must be planned before large
  data volumes because it is effectively immutable.
- Per `schema-pk-prioritize-filters`: read queries should filter on key-prefix
  dimensions such as `tenant_id`, `asset_id`, `source_id`, `point_key`, `ts`.
- Per `schema-pk-filter-on-orderby`: load PoC queries must include ORDER BY
  prefix filters to represent intended API/UI access patterns.
- Per `schema-types-native-types`: timestamps, numeric values and booleans are
  stored in typed columns, not as generic strings.
- Per `schema-types-lowcardinality`: repeated categorical strings use
  `LowCardinality(String)`.
- Per `schema-types-avoid-nullable`: current nullable typed value columns are
  semantically meaningful because one event carries exactly one typed value.
- Per `schema-partition-low-cardinality` and `schema-partition-lifecycle`:
  monthly partitions align with retention and keep partition count bounded.
- Per `schema-json-when-to-use`: raw Kafka JSON remains in landing tables, while
  known telemetry fields are extracted into typed contract columns.
- Per `insert-batch-size`: load PoC inserts default to 10K rows per batch.
- Per `insert-format-native`: production bulk load should prefer Native or
  RowBinary; the PoC uses TabSeparated for dependency-free reproducibility.
- Per `query-mv-incremental`: repeated hot rollups should eventually move from
  query views to incremental materialized rollup tables if the load PoC shows
  query-time aggregation is too expensive.
- Per `insert-optimize-avoid-final`: do not use `OPTIMIZE TABLE ... FINAL` as a
  routine dedup mechanism; use `FINAL` in correctness-first reads or a dedicated
  read model.

## Key Decisions

### Correctness-first read views before materialized analytics

**What**

`telemetry_events_dedup_v1`, `telemetry_latest_v1`, `telemetry_1m_v1` and
`telemetry_1h_v1` are query views over `telemetry_events_v1 FINAL`.

**Why**

The current ingestion path is at-least-once. Incremental rollup materialized
views fed directly from raw inserts would count replay duplicates unless we add
a separate deduplication strategy. Views over `FINAL` make API/UI semantics
correct before optimizing performance.

**Category**

derived

**Confidence**

high for MVP correctness; medium for production performance

**Source**

- `query-mv-incremental`
- `insert-optimize-avoid-final`
- https://clickhouse.com/docs/materialized-view/incremental-materialized-view
- https://clickhouse.com/docs/en/guides/replacing-merge-tree

**Validation**

Run:

```bash
uv run --env-file .env idp-telemetry-store load-poc telemetry-read-models \
  --rows 50000 \
  --points 100 \
  --batch-size 10000 \
  --duplicate-every 10
```

Expected baseline:

- `queries.dedup_count.value == logical_rows`
- `queries.latest_count.value == points`
- `queries.minute_rollup.value == logical_rows`
- `queries.hour_rollup.value == logical_rows`

### Materialized rollups are a follow-up, not the default

**What**

Do not add `AggregatingMergeTree` rollup tables until the load PoC shows query
views cannot satisfy UI/API latency targets.

**Why**

Incremental materialized views are officially recommended for repeated
real-time aggregations, but they aggregate insert blocks. With replay-prone
ReplacingMergeTree sources, they need an explicit dedup/replay design before
becoming the source of truth for charts.

**Category**

derived

**Confidence**

medium

**Source**

- `query-mv-incremental`
- `decision-real-time-preaggregation`
- https://clickhouse.com/docs/best-practices/use-materialized-views

**Validation**

Promote to materialized read models only if:

- latest or rollup views exceed the agreed query latency under representative
  row counts
- queries repeatedly scan large raw ranges
- duplicate/replay semantics are explicitly handled in the materialized path

### Keep Kafka/ClickHouse ingestion batched and decoupled

**What**

Keep Kafka Connect as the decoupled ingestion baseline and continue validating
that inserts land in healthy batches.

**Why**

The workload has bursty edge producers, replay requirements and multiple future
consumers. Kafka before ClickHouse keeps ingestion replayable and observable.

**Category**

field

**Confidence**

heuristic; depends on real producer count and event rate

**Source**

- `decision-ingestion-strategy`
- `insert-batch-size`
- https://clickhouse.com/docs/best-practices/selecting-an-insert-strategy

**Validation**

Monitor:

```sql
SELECT
    table,
    count() AS active_parts,
    sum(rows) AS rows
FROM system.parts
WHERE database = currentDatabase()
  AND active
GROUP BY table
ORDER BY active_parts DESC;
```

## Load PoC Scope

The PoC intentionally inserts directly into `telemetry_events_v1`. It isolates
ClickHouse analytical read-model behavior from Kafka Connect ingestion behavior,
which is already covered by integration tests.

The PoC does not mutate or truncate existing data. Each run uses an isolated
`tenant_id` / `asset_id` derived from `run_id`.

## Next Decision Gate

After running the PoC with representative sizes, choose one of:

- Keep query views for MVP if latency is acceptable.
- Add materialized latest-state table if latest reads are hot and slow.
- Add materialized rollup tables if chart queries repeatedly scan too many raw
  telemetry rows.
