# idp-telemetry-store

Repo-native ClickHouse migration CLI for the local and future production
`Industrial Data Platform Telemetry Store` path.

Package name and CLI entrypoint are stable identifiers:
`idp_telemetry_store` and `idp-telemetry-store`.

```bash
uv run idp-telemetry-store migrate status
uv run idp-telemetry-store migrate up
```

Configuration is read from environment variables:

- `CLICKHOUSE_HOST`
- `CLICKHOUSE_HTTP_PORT`
- `CLICKHOUSE_DATABASE`
- `CLICKHOUSE_USER`
- `CLICKHOUSE_PASSWORD`
- `CLICKHOUSE_SECURE`

By default migrations are read from `tools/idp_telemetry_store/migrations`;
the pre-production reset starts at `0001_idp_telemetry_store_v1.sql`.
Migrations are forward-only SQL files applied in filename order. Applied
checksums are tracked in `schema_migrations`; checksum drift is fatal.

## Load PoC

Run a synthetic ClickHouse read-model load PoC against an already migrated
Telemetry Store database:

```bash
uv run --env-file .env idp-telemetry-store load-poc telemetry-read-models \
  --rows 50000 \
  --points 100 \
  --batch-size 10000 \
  --duplicate-every 10
```

The command inserts batched synthetic telemetry rows into `telemetry_events_v1`
under an isolated `tenant_id`/`asset_id`, adds replay duplicates, then measures
`telemetry_events_dedup_v1`, `telemetry_latest_v1`, `telemetry_1m_v1` and
`telemetry_1h_v1`. Output is JSON so runs can be compared over time.
