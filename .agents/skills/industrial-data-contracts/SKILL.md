---
name: industrial-data-contracts
description: Use when changing or reviewing Industrial Data Platform MQTT, Kafka, ClickHouse, storage, schema versioning, migrations, producers, consumers, or contract tests. Do not use for pure wording or UI changes without contract impact.
---

# Industrial Data Contracts

Use this skill for changes where wire/storage compatibility matters.

## Read First

1. `AGENTS.md`
2. `docs/contracts/AGENTS.md`
3. The closest scoped `AGENTS.md` for affected implementation paths
4. `docs/agents/module-map.yaml`
5. The affected contract document under `docs/contracts/`

## Contract Rules

- Treat `docs/contracts/` as the source of truth for MQTT/Kafka/ClickHouse
  names, fields, schemas, and compatibility.
- Preserve v1 compatibility for stable `idp.*`/`idp/v1` identifiers. Breaking
  changes need a new contract version and a migration/rollout plan.
- Do not rename MQTT `idp/v1`, Kafka `idp.*`, ClickHouse tables/views, or
  contract ids as part of product naming.
- Keep ClickHouse migrations forward-only and checksum-stable after application.
- Keep `alarm_history_events_v1`; it is a storage sink for the future Alarm
  Management Module writer.
- If an ADR is needed, document the resulting implementation in living
  contracts, guides, or C4 docs after the decision is made.

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

- Contract surface changed: topic/table/schema/config/migration.
- Source of truth checked: exact contract docs and scoped `AGENTS.md`.
- Compatibility decision: backward-compatible or new version required.
- Producers/consumers/storage paths checked.
- Docs/C4/ADR follow-up: completed or not needed.
- Validation: exact commands run, or skipped with reason.
