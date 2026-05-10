# ClickHouse Telemetry Store Guide

Scope: `tools/idp_telemetry_store/`.

This package owns repo-native migration and load-PoC tooling for the Industrial
Data Platform Telemetry Store.

## Do

- Keep migration files forward-only and checksum-stable after application.
- Treat `docs/contracts/clickhouse/telemetry-store.v1.md` as the storage
  contract source of truth.
- Preserve ClickHouse table/view names unless a new contract version and
  migration plan are approved.
- Keep load-PoC output machine-readable.

## Do Not

- Do not rewrite already-applied migrations.
- Do not optimize DDL for production without a load PoC result.
- Do not remove `alarm_history_events_v1`; it is a storage sink owned by the
  future Alarm Management Module writer.

## Validation

- `uv run --package idp-telemetry-store pytest tools/idp_telemetry_store/tests`
- For storage path:
  `uv run --group integration pytest tests/integration/test_kafka_to_clickhouse_storage.py`
