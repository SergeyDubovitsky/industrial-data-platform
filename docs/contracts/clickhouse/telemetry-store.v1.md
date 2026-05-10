# `idp.telemetry-store.clickhouse.telemetry-store.v1`

Дата: 2026-05-10
Статус: working draft

Этот контракт фиксирует начальную migration-backed физическую модель
`Telemetry Store` на базе ClickHouse. Он нужен для review, проверки
совместимости Kafka consumers и сопровождения fresh baseline migration
`0001_idp_telemetry_store_v1.sql`. Физическая схема еще не считается
production-validated performance schema до нагрузочного PoC.

`Telemetry Store` принадлежит `Industrial Data Platform`.
Таблицы и view names не переименовываются. `alarm_history_events_v1` остается
storage sink в `Telemetry Store`, но writer/owner этого потока находится в
`Alarm Management Module`.

## Tables

| Table | Назначение | Writer |
| --- | --- | --- |
| `telemetry_events_v1` | Raw/canonical telemetry events, одна строка на наблюдение точки | `telemetry-store-writer.v1` |
| `source_config_snapshots_v1` | Исторические snapshots source config revisions | `telemetry-store-writer.v1` |
| `source_connection_events_v1` | История southbound source connection states | `telemetry-store-writer.v1` |
| `agent_status_events_v1` | История agent online/offline status | `telemetry-store-writer.v1` |
| `derived_events_v1` | Derived events from Streaming Analytics | `telemetry-store-writer.v1`, `streaming-analytics.v1` |
| `alarm_history_events_v1` | Immutable alarm lifecycle history storage sink; writer-owned by `Alarm Management Module` | `alarm-rule-engine.v1` |
| `telemetry_events_dedup_v1` | Deduplicated view для безопасного чтения истории telemetry | query view |
| `telemetry_latest_v1` | Последнее значение по точке для быстрых UI/API запросов | query view |
| `telemetry_1m_v1` | Correctness-first rollup view по точке за 1 минуту | query view |
| `telemetry_1h_v1` | Correctness-first rollup view по точке за 1 час | query view |

## Kafka landing tables

Fresh baseline migration создает raw landing tables для Kafka Connect Sink. Они являются
техническим слоем между Kafka topics и contract tables; доменный transform
выполняется materialized views в той же baseline migration.

| Kafka topic | Landing table |
| --- | --- |
| `idp.telemetry.events.v1` | `kafka_telemetry_events_raw_v1` |
| `idp.source.configs.v1` | `kafka_source_configs_raw_v1` |
| `idp.source.connections.v1` | `kafka_source_connections_raw_v1` |
| `idp.agent.status.v1` | `kafka_agent_status_raw_v1` |
| `idp.derived.events.v1` | `kafka_derived_events_raw_v1` |

Initial landing shape:

```sql
payload_json String,
ingested_at DateTime64(3, 'UTC') DEFAULT now64(3)
```

Kafka metadata columns (`topic`, `partition`, `offset`, `key`, `timestamp`) are
not part of the initial migration until the Kafka Connect StringConverter PoC
confirms reliable metadata population without connector-side domain mapping.

## Materialized views

Baseline migration создает materialized views для преобразования raw landing rows
в contract tables:

| Landing table | Materialized view | Target table |
| --- | --- | --- |
| `kafka_telemetry_events_raw_v1` | `telemetry_events_from_raw_mv_v1` | `telemetry_events_v1` |
| `kafka_source_configs_raw_v1` | `source_config_snapshots_from_raw_mv_v1` | `source_config_snapshots_v1` |
| `kafka_source_connections_raw_v1` | `source_connection_events_from_raw_mv_v1` | `source_connection_events_v1` |
| `kafka_agent_status_raw_v1` | `agent_status_events_from_raw_mv_v1` | `agent_status_events_v1` |
| `kafka_derived_events_raw_v1` | `derived_events_from_raw_mv_v1` | `derived_events_v1` |

MV layer owns domain parsing from `payload_json`.

- Required Kafka payload fields are validated with fail-fast ClickHouse
  expressions.
- Invalid landing inserts are rejected by the MV and, with Kafka Connect
  `errors.tolerance=all`, are routed to
  `idp.telemetry-store.dlq.v1`.
- Polymorphic Kafka `value` is mapped to typed ClickHouse columns:
  `number -> value_float`, `boolean -> value_bool`,
  `string -> value_string`.
- Optional JSON payloads such as `points`, `source_event_ids` and `attributes`
  are stored as JSON strings in the corresponding `*_json` columns.

## Raw telemetry model

`telemetry_events_v1` хранит узкую событийную модель:

- одна строка = одно наблюдение одной точки в один момент времени
- добавление нового тега/датчика не требует `ALTER TABLE`
- значение хранится в typed value columns, а не в отдельной колонке на датчик
- мультитенантность задается обязательным `tenant_id`
- дедупликация выполняется по `idempotency_key`

Обязательные поля `telemetry_events_v1`:

| Column | Type draft | Назначение |
| --- | --- | --- |
| `tenant_id` | `String` | Клиент/tenant платформы |
| `event_id` | `String` | Непрозрачный id события от edge, не UUID-only |
| `idempotency_key` | `String` | `{tenant_id}|{asset_id}|{agent_id}|{event_id}` |
| `asset_id` | `String` | Объект мониторинга |
| `agent_id` | `String` | Edge agent instance |
| `source_id` | `String` | Source внутри agent |
| `source_type` | `LowCardinality(String)` | Тип source: `knx`, `modbus`, `opc-ua`, ... |
| `point_id` | `String` | Стабильный platform registry id точки; MVP fallback до Platform Registry: `{tenant_id}|{asset_id}|{source_id}|{point_key}` |
| `point_key` | `String` | MQTT-safe key точки |
| `point_ref` | `String` | Исходный protocol point reference |
| `source_config_revision` | `String` | Версия source config |
| `ts` | `DateTime64(3, 'UTC')` | Время наблюдения |
| `ingested_at` | `DateTime64(3, 'UTC')` | Время ingestion в платформу |
| `event_type` | `LowCardinality(String)` | `telemetry.changed` / `telemetry.sample` |
| `observation_mode` | `LowCardinality(String)` | `listen`, `read_on_start`, `periodic_read` |
| `value_type` | `LowCardinality(String)` | `boolean`, `number`, `string` |
| `value_float` | `Nullable(Float64)` | Numeric value |
| `value_bool` | `Nullable(Bool)` | Boolean value |
| `value_string` | `Nullable(String)` | String value |
| `value_raw` | `Nullable(String)` | Raw protocol value |
| `quality` | `LowCardinality(String)` | `good`, `uncertain`, `bad` |
| `sequence` | `UInt64` | Sequence внутри точки/agent |

Draft engine:

```sql
CREATE TABLE telemetry_events_v1
(
    tenant_id String,
    event_id String,
    idempotency_key String,
    asset_id String,
    agent_id String,
    source_id String,
    source_type LowCardinality(String),
    point_id String,
    point_key String,
    point_ref String,
    source_config_revision String,
    ts DateTime64(3, 'UTC'),
    ingested_at DateTime64(3, 'UTC'),
    event_type LowCardinality(String),
    observation_mode LowCardinality(String),
    value_type LowCardinality(String),
    value_float Nullable(Float64),
    value_bool Nullable(Bool),
    value_string Nullable(String),
    value_raw Nullable(String),
    quality LowCardinality(String),
    sequence UInt64
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(ts)
ORDER BY (tenant_id, asset_id, source_id, point_key, ts, idempotency_key)
TTL ts + INTERVAL 180 DAY DELETE;
```

## Read and dedup conventions

Kafka Connect path в MVP работает в at-least-once режиме. Один и тот же Kafka
record может быть записан в landing/contract tables повторно после retry,
rebalance или restart. Поэтому `ReplacingMergeTree` tables являются
eventual-dedup storage layer, а не мгновенно уникальным state API.

Правила чтения:

- API/UI-запросы, которым нужна уникальность по `idempotency_key`, должны читать
  `ReplacingMergeTree` contract tables с `FINAL` или через отдельные
  deduplicated query views.
- Raw landing tables (`kafka_*_raw_v1`) являются append-only diagnostic layer;
  их нельзя использовать как пользовательский источник истины для счетчиков
  событий без явной дедупликации.
- History/status tables на `MergeTree` (`source_connection_events_v1`,
  `agent_status_events_v1`) сохраняют события как историю. Если upstream
  повторит тот же status event, downstream read model должен решать, считать ли
  это дублем или повторным наблюдением.
- Latest-state и rollup tables/views (`telemetry_latest_v1`,
  `telemetry_1m_v1`, `telemetry_1h_v1`) должны строиться с учетом
  `idempotency_key`/`FINAL` semantics, когда источником являются raw contract
  tables.

Baseline migration добавляет correctness-first query views поверх
`telemetry_events_v1 FINAL`:

- `telemetry_events_dedup_v1` возвращает deduplicated telemetry history.
- `telemetry_latest_v1` возвращает последнее событие по grain
  `tenant_id + asset_id + source_id + point_key`.
- `telemetry_1m_v1` и `telemetry_1h_v1` агрегируют deduplicated события по
  минутному/часовому bucket.

Эти views являются безопасным API/UI baseline, но не production performance
optimization. Материализованные latest/rollup tables можно добавить отдельной
миграцией после нагрузочного PoC и явной стратегии dedup/replay для rollups.

## Snapshot and status tables

`source_config_snapshots_v1`:

- key fields: `tenant_id`, `asset_id`, `agent_id`, `source_id`, `source_config_revision`
- payload fields: `source_type`, `points_json`, `ts`, `ingested_at`
- engine draft: `ReplacingMergeTree(ingested_at)`
- partition: `toYYYYMM(ts)`
- order key: `(tenant_id, asset_id, agent_id, source_id, source_config_revision)`
- retention: `400d`

`source_connection_events_v1`:

- key fields: `tenant_id`, `asset_id`, `agent_id`, `source_id`
- payload fields: `state`, `reason`, `ts`, `ingested_at`
- engine draft: `MergeTree`
- partition: `toYYYYMM(ts)`
- order key: `(tenant_id, asset_id, source_id, ts)`
- retention: `400d`

`agent_status_events_v1`:

- key fields: `tenant_id`, `asset_id`, `agent_id`
- payload fields: `status`, `ts`, `ingested_at`
- engine draft: `MergeTree`
- partition: `toYYYYMM(ts)`
- order key: `(tenant_id, asset_id, agent_id, ts)`
- retention: `400d`

## Derived and alarm tables

`derived_events_v1`:

- key fields: `tenant_id`, `derived_event_id`, `idempotency_key`, `asset_id`
- payload fields: `rule_or_metric_id`, `event_type`, `ts`, `produced_at`,
  typed value columns, `attributes_json`
- engine draft: `ReplacingMergeTree(produced_at)`
- partition: `toYYYYMM(ts)`
- order key: `(tenant_id, asset_id, event_type, ts, idempotency_key)`
- retention: `180d`

`alarm_history_events_v1`:

- key fields: `tenant_id`, `alarm_event_id`, `alarm_id`, `asset_id`
- payload fields: `event_type`, `severity`, `state`, `operator_id`,
  `reason`, `ts`, `ingested_at`, `payload_json`
- engine draft: `ReplacingMergeTree(ingested_at)`
- partition: `toYYYYMM(ts)`
- order key: `(tenant_id, asset_id, alarm_id, ts, alarm_event_id)`
- retention: `5y`

## Rollups and latest values

`telemetry_1m_v1`:

- grain: `tenant_id + asset_id + source_id + point_key + toStartOfMinute(ts)`
- shape: query view over `telemetry_events_dedup_v1`
- value columns: `event_count`, `good_count`, `uncertain_count`, `bad_count`,
  `number_count`, `value_min`, `value_max`, `value_avg`, `value_last`
- retention: inherited from `telemetry_events_v1`

`telemetry_1h_v1`:

- grain: `tenant_id + asset_id + source_id + point_key + toStartOfHour(ts)`
- shape: query view over `telemetry_events_dedup_v1`
- value columns: `event_count`, `good_count`, `uncertain_count`, `bad_count`,
  `number_count`, `value_min`, `value_max`, `value_avg`, `value_last`
- retention: inherited from `telemetry_events_v1`

`telemetry_latest_v1`:

- grain: `tenant_id + asset_id + source_id + point_key`
- value columns mirror latest telemetry typed value columns
- shape: query view over `telemetry_events_dedup_v1`
- retention: inherited from `telemetry_events_v1`

## Compatibility

- Renaming a table or changing primary `ORDER BY` is breaking and requires a new
  table/version suffix.
- Adding nullable analytical columns is backward-compatible if writers and
  readers tolerate missing values.
- `tenant_id` must be present in every `Telemetry Store` table.
- `idempotency_key` is stored as `String`; ClickHouse must not require UUID-only
  `event_id`.
