# Decision Register

Дата: 2026-05-10
Статус: working register

Этот документ заменяет ADR как default navigation для людей и AI-agent. Он
фиксирует активные архитектурные решения компактно и указывает, где находится
текущая документация. Полные ADR сохранены только как исторический rationale в
`docs/architecture/adrs/archive/`.

## Как использовать

- Для текущих фактов сначала читайте `current-state.md`, `glossary.md`,
  `docs/contracts/` и LikeC4-модель в `arch/likec4/`.
- Для истории выбора, trade-off и отклоненных альтернатив открывайте архивный
  ADR из последней колонки.
- Если contract doc и архивный ADR расходятся по полям, topic/table names или
  schema details, contract doc является source of truth.

## Активные решения

| ID | Статус | Активное решение | Текущий source of truth | Архивный rationale |
| --- | --- | --- | --- | --- |
| ADR-001 | accepted | `KNX` MVP подключается напрямую через `xknx` и `KNXnet/IP Tunneling`; `knxd` не является runtime-компонентом. | `solution-architecture.md`, `arch/likec4/systems/edge-telemetry-agent/` | `adrs/archive/ADR-001-runtime-topology.md` |
| ADR-002 | accepted | Сбор использует гибрид `listen + selective read`: passive events основной поток, `read_on_start`/`periodic_read` только для whitelist endpoints. | `solution-architecture.md`, `apps/edge_telemetry_agent/docs/data-contracts.md` | `adrs/archive/ADR-002-acquisition-mode.md` |
| ADR-003 | partially superseded | Edge хранит техническое состояние в SQLite: point state cache для warm restart и delivery outbox для retry. | `docs/contracts/edge-telemetry-agent/sqlite-storage.v1.md`, `solution-architecture.md` | `adrs/archive/ADR-003-buffering-and-delivery.md` |
| ADR-004 | accepted | Runtime identity model: `tenant_id`, `asset_id`, `agent_id`, `source_id`, `point_ref`, `point_key`, `config_revision`, `source_config_revision`. | `current-state.md`, `docs/contracts/edge-telemetry-agent/`, `docs/contracts/platform-ingestion/` | `adrs/archive/ADR-004-universal-agent-configuration.md` |
| ADR-005 | accepted | `MQTT 5.0` is the edge transport for telemetry, config projection, source connection status and agent LWT/status topic tree. | `docs/contracts/edge-telemetry-agent/mqtt-topic-tree.v1.md`, `apps/edge_telemetry_agent/docs/mqtt-topics.md` | `adrs/archive/ADR-005-mqtt-event-transport.md` |
| ADR-006 | accepted | The repo remains a monorepo with coordinated `apps`, `libs`, `tools`, `infra`, `environments`, `arch`, `docs`, and a single Python `uv` workspace. | `README.md`, `AGENTS.md`, `docs/agents/module-map.yaml` | `adrs/archive/ADR-006-mvp-monorepo-structure.md` |
| ADR-007 | partially superseded | Platform storage uses `ClickHouse` for telemetry/analytics and `PostgreSQL` for mutable platform/config/workflow state. Product boundary terminology is now `Industrial Data Platform`. | `docs/contracts/clickhouse/telemetry-store.v1.md`, `current-state.md`, `solution-architecture.md` | `adrs/archive/ADR-007-monitoring-platform-data-stores.md` |
| ADR-008 | accepted | Edge runtime config is server-issued: local bootstrap plus retained MQTT agent runtime/source configs. YAML bundle is import/bootstrap tooling. | `docs/contracts/edge-telemetry-agent/`, `docs/contracts/edge-telemetry-agent/config-bundle.v1.md`, `current-state.md` | `adrs/archive/ADR-008-server-issued-edge-runtime-configuration.md` |
| ADR-009 | accepted | Kafka-to-ClickHouse baseline uses Kafka Connect/ClickHouse sink into raw landing tables and materialized views. | `docs/contracts/clickhouse/telemetry-store.v1.md`, `docs/contracts/kafka/topics.v1.md` | `adrs/archive/ADR-009-kafka-to-clickhouse-ingestion.md` |
| ADR-010 | accepted | First config backend slice is `Config Registry`: FastAPI async, SQLAlchemy, PostgreSQL, clean architecture, rendered config revisions and transactional outbox. | `apps/idp_config_registry/README.md`, `docs/contracts/edge-telemetry-agent/config-revision-model.md` | `adrs/archive/ADR-010-platform-configuration-backend.md` |
| ADR-011 | accepted | Internal backoffice for Config Registry uses SQLAdmin; write actions go through application use cases and transactional outbox boundaries. | `apps/idp_config_registry/README.md` | `adrs/archive/ADR-011-internal-backoffice-admin-ui.md` |
| ADR-012 | accepted | `Kafka Event Log` is the logical stream. Local runtime uses Apache Kafka plus Redpanda Connect/Kafka Connect; Redpanda broker stays a PoC candidate. | `docs/contracts/kafka/topics.v1.md`, `infra/local/README.md` | `adrs/archive/ADR-012-kafka-redpanda-runtime-baseline.md` |
| ADR-013 | accepted | Post-MVP direction: cloud-first Russian pilot, local Docker dev/test baseline, `OPC UA` read-only ingestion track, internal-only execution backlog. | `current-state.md`, `solution-architecture.md`, `open-questions.md` | `adrs/archive/ADR-013-post-mvp-product-and-execution-governance.md` |
| ADR-014 | accepted | Central core is `Industrial Data Platform`; `Web Monitoring Module` and `Alarm Management Module` are separate modules above it. Runtime/contract identifiers stay `idp.*`/`idp/v1`. | `current-state.md`, `arch/likec4/`, `docs/contracts/README.md` | `adrs/archive/ADR-014-data-platform-core-and-modules.md` |

## Maintenance

New architecture decisions should update this register and the relevant living
source-of-truth documents. Add a new ADR only when the team needs durable
rationale for a significant trade-off, then archive it after the active facts are
folded into living docs.
