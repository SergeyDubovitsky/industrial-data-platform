---
title: Contracts
description: Contract registry reading path for MQTT, Kafka, ClickHouse, and edge storage.
---

`docs/contracts/` is the canonical source of truth for data and storage
contracts. Living architecture docs may summarize these contracts, but they must
not redefine fields, topic names, table names, or compatibility rules.

## Contract areas

- `docs/contracts/edge-telemetry-agent/`: bootstrap config, retained runtime
  config, source config, MQTT messages, topic tree, and edge SQLite state.
- `docs/contracts/platform-ingestion/`: MQTT-to-Kafka mapping, tenant/point
  enrichment, and ingestion errors.
- `docs/contracts/kafka/`: Kafka-compatible topic names, keys, value schemas,
  retention, compaction, and consumer groups.
- `docs/contracts/clickhouse/`: ClickHouse contract tables, landing tables,
  materialized views, read models, rollups, and retention.

## Compatibility

Do not rename stable identifiers without an explicit migration plan:

- MQTT topic tree `idp/v1/...`
- Kafka topics and message ids with `idp.*`
- ClickHouse table/view names and migration filenames
- Contract ids under `docs/contracts/`

When contracts and rationale disagree, contracts win.
