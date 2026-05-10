---
name: industrial-data-contracts
description: Use when changing or reviewing Industrial Data Platform MQTT, Kafka, ClickHouse, storage, schema versioning, migrations, producers, consumers, or contract tests. Do not use for pure wording or UI changes without contract impact.
---

# Industrial Data Contracts

Use this skill for changes where wire/storage compatibility matters.

## Read First

1. `AGENTS.md`
2. `docs/contracts/AGENTS.md`
3. `docs/agents/module-map.yaml`
4. The affected contract document under `docs/contracts/`

## Contract Rules

- Treat `docs/contracts/` as the source of truth for MQTT/Kafka/ClickHouse
  names, fields, schemas, and compatibility.
- Preserve v1 compatibility. Breaking changes need a new contract version and a
  migration/rollout plan.
- Do not rename MQTT `wm/v1`, Kafka `wm.platform.*`, ClickHouse tables/views, or
  contract ids as part of product naming.
- Keep ClickHouse migrations forward-only and checksum-stable after application.
- Keep `alarm_history_events_v1`; it is a storage sink for the future Alarm
  Management Module writer.

## Workflow

1. Identify the affected surface: MQTT topic/payload, Kafka topic/message,
   ClickHouse table/view, edge config, SQLite local state, or migration.
2. List producers, consumers, storage writers, and tests that depend on it.
3. Update the canonical contract first, then implementation, tests, and guides.
4. If the data flow or ownership boundary changes, check whether ADR or LikeC4
   updates are required.
5. Run the validation commands from `docs/agents/module-map.yaml` for the
   affected module and data path.

## Output

- Contract surface changed.
- Compatibility decision: backward-compatible or new version required.
- Producers/consumers/storage paths checked.
- Validation run or intentionally not run.
