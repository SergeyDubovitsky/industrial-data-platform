# ADR-010: Backend хранения настроек платформы

Дата: 2026-05-03  
Статус: accepted

Примечание 2026-05-10: после `ADR-014` `Config Registry` относится к
`Industrial Data Platform` core. Термины `Monitoring & Alarm Platform` и
`Platform API` в этом ADR остаются историческим контекстом первого backend-среза
и не означают, что config backend должен расширяться до Web Monitoring или Alarm
Management API без отдельного решения.

Примечание 2026-05-17: физическая PostgreSQL-схема из разделов ниже
сохранена как исторический baseline и переопределена реализацией issue 18.
Актуальная схема `Config Registry` использует internal `id uuid primary key`,
UUID foreign keys и per-table public `code` columns в registry tables. В
domain/application layer используются явные `tenant_code`, `asset_code`,
`agent_code`, `source_code`, `point_code`; denormalized revision/outbox
snapshots хранят `tenant_code`, `asset_code`, `agent_code`, `source_code`.
Публичные wire/API identifiers `tenant_id`, `asset_id`, `agent_id`, `source_id`,
`point_id` остаются контрактной поверхностью HTTP/Kafka/MQTT.
Текущий source of truth:
[Config Registry README](../../../../apps/idp_config_registry/README.md) и
[Runtime и Source Config Revisions](../../../contracts/edge-telemetry-agent/config-revision-model.md).

## Контекст

Следующий backend-инкремент нужен не для всей `Monitoring & Alarm Platform`
сразу, а только для хранения и управления настройками:

- tenants
- assets
- edge agents
- sources
- points
- agent runtime/source config revisions
- jobs/results публикации Kafka edge config delivery records

Этот backend должен стать будущим source of truth для данных, из которых
формируются контракты:

- `idp.edge.agent-runtime-config.v1`
- `idp.edge.source-config.v1`
- `idp.edge.config.status.v1`
- `idp.source.config.v1`
- `idp.edge.config.delivery.v1`

Вне этого ADR:

- аутентификация, пользователи, роли, Keycloak и JWT
- `Platform Frontend`
- internal `Backoffice Admin UI`
- `Alarm Rule Engine`
- `Notification Service`
- `Streaming Analytics`
- `Telemetry Store` read API
- `API Gateway`

Каждая из этих областей должна получить отдельный ADR перед реализацией.

## Решение

Для первого backend-инкремента принимается один сервис:

- `Config Registry`

Это HTTP API для хранения и выдачи настроек платформы. В LikeC4 он остается
частью контейнера `Platform API`, но scope реализации ограничен только
configuration backend.

Технологический стек:

- `Python`
- `FastAPI` в async-режиме
- `Pydantic v2` для request/response DTO и validation
- `SQLAlchemy 2.x async`
- `asyncpg`
- `PostgreSQL`
- `Alembic`

Аутентификация в этом инкременте не реализуется. Для локальной разработки и
integration-тестов API считается внутренним trusted API. Безопасность,
пользователи и роли будут зафиксированы отдельным ADR.

## Архитектурный стиль

Backend строится по clean architecture / ports-and-adapters подходу.

Зависимости направлены только внутрь:

```text
FastAPI routers
  -> application use cases
  -> repository protocols / unit of work protocols
  -> SQLAlchemy adapters
  -> PostgreSQL
```

Правила:

- routers не содержат бизнес-логику и не импортируют SQLAlchemy models напрямую
- use cases не импортируют FastAPI и SQLAlchemy
- domain models не зависят от web framework и database framework
- persistence реализует repository protocols
- транзакционные сценарии используют Unit of Work
- Pydantic DTO не являются ORM-моделями и не являются domain entities
- все write operations проходят через use case, где валидируются инварианты

Рекомендуемая структура будущего приложения:

```text
apps/idp_config_registry/
├── src/idp_config_registry/
│   ├── api/
│   │   ├── routers/
│   │   └── schemas/
│   ├── application/
│   │   ├── ports/
│   │   └── use_cases/
│   ├── domain/
│   │   ├── entities.py
│   │   └── value_objects.py
│   ├── infrastructure/
│   │   ├── postgres/
│   │   └── config_renderer/
│   └── settings.py
├── migrations/
└── tests/
```

## Доменная модель

### Tenant

`Tenant` — клиент/tenant платформы.

Поля:

- `tenant_id`
- `name`
- `status`
- `created_at`
- `updated_at`

Инварианты:

- `tenant_id` обязателен
- `tenant_id` используется во всех таблицах платформенных настроек
- удаление tenant не выполняется физически в первом инкременте

### Object

`Object` — объект мониторинга/автоматизации внутри tenant.

Поля:

- `tenant_id`
- `asset_id`
- `name`
- `description`
- `status`
- `created_at`
- `updated_at`

Инварианты:

- `(tenant_id, asset_id)` уникален
- `asset_id` должен соответствовать MQTT path-id contract:
  `^[a-z0-9][a-z0-9_-]{0,127}$`

### Agent

`Agent` — зарегистрированный экземпляр `Edge Telemetry Agent`.

Поля:

- `tenant_id`
- `asset_id`
- `agent_id`
- `name`
- `status`
- `bootstrap_hint_json`
- `created_at`
- `updated_at`

`bootstrap_hint_json` хранит только подсказки для пусконаладки: MQTT endpoint
profile, expected credentials refs, local storage profile. Это не runtime
registry точек.

Инварианты:

- `(tenant_id, asset_id, agent_id)` уникален
- `agent_id` должен соответствовать MQTT path-id contract

### Source

`Source` — конкретное подключение агента к protocol source.

Поля:

- `tenant_id`
- `asset_id`
- `agent_id`
- `source_id`
- `source_type`
- `enabled`
- `name`
- `description`
- `connection_json`
- `acquisition_defaults_json`
- `publish_defaults_json`
- `created_at`
- `updated_at`

Инварианты:

- `(tenant_id, asset_id, agent_id, source_id)` уникален
- `source_id` должен соответствовать MQTT path-id contract
- `source_type` задает тип адаптера: `knx`, `modbus`, `opc-ua`, `db` или
  другой поддержанный source type
- `connection_json` не хранит plain text secrets; допускаются только secret refs
  или несекретные параметры подключения

### Point

`Point` — точка мониторинга внутри source.

Поля:

- `tenant_id`
- `asset_id`
- `agent_id`
- `source_id`
- `point_id`
- `point_key`
- `point_ref`
- `name`
- `description`
- `value_type`
- `value_model`
- `signal_type`
- `unit`
- `enabled`
- `acquisition_json`
- `publish_json`
- `tags_json`
- `created_at`
- `updated_at`

Инварианты:

- `(tenant_id, point_id)` уникален
- `(tenant_id, asset_id, agent_id, source_id, point_key)` уникален
- `(tenant_id, asset_id, agent_id, source_id, point_ref)` уникален
- `point_key` должен соответствовать contract pattern:
  `^(?:[A-Za-z0-9._~-]|%[0-9A-F]{2})+$`
- `point_key` строится обратимо из `point_ref`
- `value_type` принимает `boolean`, `number`, `string`
- `signal_type` принимает `command`, `feedback`, `status`, `sensor`
- `command` points не публикуются как telemetry по умолчанию

### Agent Runtime Config Revision

`AgentRuntimeConfigRevision` — версия root agent runtime config агента.

Поля:

- `tenant_id`
- `asset_id`
- `agent_id`
- `config_revision`
- `status`
- `issued_at`
- `agent_runtime_payload_json`
- `created_at`

Инварианты:

- `(tenant_id, asset_id, agent_id, config_revision)` уникален
- `agent_runtime_payload_json` должен валидироваться как `idp.edge.agent-runtime-config.v1`
- active revision на одного agent может быть только одна

### Source Config Revision

`SourceConfigRevision` — версия source config для одного `source_id`.

Поля:

- `tenant_id`
- `asset_id`
- `agent_id`
- `source_id`
- `source_config_revision`
- `config_revision`
- `status`
- `issued_at`
- `source_payload_json`
- `created_at`

Инварианты:

- `(tenant_id, asset_id, agent_id, source_id, source_config_revision)` уникален
- `source_payload_json` должен валидироваться как `idp.edge.source-config.v1`
- `config_revision` связывает source revision с root agent runtime revision

### Config Outbox Record

`ConfigOutboxRecord` — transactional outbox record для Kafka-first delivery
config events.

Поля:

- `tenant_id`
- `outbox_id`
- `asset_id`
- `agent_id`
- `config_revision`
- `config_scope`
- `source_id`
- `source_config_revision`
- `message_type`
- `kafka_topic`
- `kafka_key`
- `payload_json`
- `status`
- `created_at`
- `available_at`
- `lease_expires_at`
- `published_at`
- `attempt_count`
- `next_attempt_at`
- `last_error`

Отдельные `ConfigPublishJob` / `ConfigPublishResult` сущности на текущем
инкременте не вводятся. Их ответственность покрывает одна таблица
`config_outbox`: она одновременно хранит delivery envelope, статус публикации,
lease, попытки, `published_at` и последнюю ошибку. Это проще для MVP и
соответствует фактической реализации.

## PostgreSQL physical model draft

Минимальный набор таблиц первого инкремента:

| Table | Назначение |
| --- | --- |
| `tenants` | Tenants платформы |
| `assets` | Объекты мониторинга |
| `agents` | Edge agent registry |
| `sources` | Source registry и source-level defaults |
| `points` | Point registry и point-level policies |
| `agent_runtime_config_revisions` | Rendered `idp.edge.agent-runtime-config.v1` payloads |
| `source_config_revisions` | Rendered `idp.edge.source-config.v1` payloads |
| `config_outbox` | Единственная transactional outbox таблица для Kafka-first delivery config events, статусов публикации, retry/lease и ошибок |
| `schema_migrations` | Alembic-managed migrations |

Общие правила:

- все domain tables содержат `tenant_id`
- все таблицы имеют `created_at`
- mutable registry tables имеют `updated_at`
- hard delete в первом инкременте не используется; нужен `status` или
  `enabled=false`
- JSONB используется для protocol-specific settings и policies, но stable
  identity fields выносятся в отдельные колонки
- rendered payloads сохраняются как JSONB snapshots, чтобы audit/debug мог
  показать, что именно было опубликовано

### Table structure draft

`tenants`

| Column | Type draft | Constraints / notes |
| --- | --- | --- |
| `tenant_id` | `text` | `primary key`, MQTT/path-safe id не требуется, но значение должно быть стабильным |
| `name` | `text` | `not null` |
| `status` | `text` | `not null`, enum-like: `active`, `disabled` |
| `created_at` | `timestamptz` | `not null` |
| `updated_at` | `timestamptz` | `not null` |

`assets`

| Column | Type draft | Constraints / notes |
| --- | --- | --- |
| `tenant_id` | `text` | `not null`, FK -> `tenants.tenant_id` |
| `asset_id` | `text` | `not null`, MQTT path-id pattern |
| `name` | `text` | `not null` |
| `description` | `text` | nullable |
| `status` | `text` | `not null`, enum-like: `active`, `disabled` |
| `created_at` | `timestamptz` | `not null` |
| `updated_at` | `timestamptz` | `not null` |

Keys:

- primary key: `(tenant_id, asset_id)`
- index: `(tenant_id, status)`

`agents`

| Column | Type draft | Constraints / notes |
| --- | --- | --- |
| `tenant_id` | `text` | `not null` |
| `asset_id` | `text` | `not null` |
| `agent_id` | `text` | `not null`, MQTT path-id pattern |
| `name` | `text` | nullable |
| `status` | `text` | `not null`, enum-like: `active`, `disabled`, `retired` |
| `bootstrap_hint_json` | `jsonb` | `not null default '{}'`, no plain text secrets |
| `created_at` | `timestamptz` | `not null` |
| `updated_at` | `timestamptz` | `not null` |

Keys:

- primary key: `(tenant_id, asset_id, agent_id)`
- FK: `(tenant_id, asset_id)` -> `assets`
- index: `(tenant_id, agent_id)`

`sources`

| Column | Type draft | Constraints / notes |
| --- | --- | --- |
| `tenant_id` | `text` | `not null` |
| `asset_id` | `text` | `not null` |
| `agent_id` | `text` | `not null` |
| `source_id` | `text` | `not null`, MQTT path-id pattern |
| `source_type` | `text` | `not null`, examples: `knx`, `modbus`, `opc-ua`, `db` |
| `enabled` | `boolean` | `not null default true` |
| `name` | `text` | nullable |
| `description` | `text` | nullable |
| `connection_json` | `jsonb` | `not null default '{}'`, secret refs only |
| `acquisition_defaults_json` | `jsonb` | `not null` |
| `publish_defaults_json` | `jsonb` | `not null` |
| `created_at` | `timestamptz` | `not null` |
| `updated_at` | `timestamptz` | `not null` |

Keys:

- primary key: `(tenant_id, asset_id, agent_id, source_id)`
- FK: `(tenant_id, asset_id, agent_id)` -> `agents`
- index: `(tenant_id, asset_id, source_type)`

`points`

| Column | Type draft | Constraints / notes |
| --- | --- | --- |
| `tenant_id` | `text` | `not null` |
| `asset_id` | `text` | `not null` |
| `agent_id` | `text` | `not null` |
| `source_id` | `text` | `not null` |
| `point_id` | `text` | `not null`, stable platform id |
| `point_key` | `text` | `not null`, MQTT-safe point key pattern |
| `point_ref` | `text` | `not null`, protocol reference |
| `name` | `text` | `not null` |
| `description` | `text` | nullable |
| `value_type` | `text` | `not null`, enum-like: `boolean`, `number`, `string` |
| `value_model` | `text` | `not null` |
| `signal_type` | `text` | `not null`, enum-like: `command`, `feedback`, `status`, `sensor` |
| `unit` | `text` | nullable |
| `enabled` | `boolean` | `not null default true` |
| `acquisition_json` | `jsonb` | `not null` |
| `publish_json` | `jsonb` | `not null` |
| `tags_json` | `jsonb` | `not null default '{}'` |
| `created_at` | `timestamptz` | `not null` |
| `updated_at` | `timestamptz` | `not null` |

Keys:

- primary key: `(tenant_id, point_id)`
- unique: `(tenant_id, asset_id, agent_id, source_id, point_key)`
- unique: `(tenant_id, asset_id, agent_id, source_id, point_ref)`
- FK: `(tenant_id, asset_id, agent_id, source_id)` -> `sources`
- index: `(tenant_id, asset_id, agent_id, source_id, enabled)`

`agent_runtime_config_revisions`

| Column | Type draft | Constraints / notes |
| --- | --- | --- |
| `tenant_id` | `text` | `not null` |
| `asset_id` | `text` | `not null` |
| `agent_id` | `text` | `not null` |
| `config_revision` | `text` | `not null` |
| `status` | `text` | `not null`, enum-like: `draft`, `rendered`, `active`, `superseded`, `failed` |
| `issued_at` | `timestamptz` | `not null` |
| `agent_runtime_payload_json` | `jsonb` | `not null`, validates `idp.edge.agent-runtime-config.v1` |
| `created_at` | `timestamptz` | `not null` |

Keys:

- primary key: `(tenant_id, asset_id, agent_id, config_revision)`
- FK: `(tenant_id, asset_id, agent_id)` -> `agents`
- partial unique index for active revision: `(tenant_id, asset_id, agent_id)` where `status = 'active'`

`source_config_revisions`

| Column | Type draft | Constraints / notes |
| --- | --- | --- |
| `tenant_id` | `text` | `not null` |
| `asset_id` | `text` | `not null` |
| `agent_id` | `text` | `not null` |
| `source_id` | `text` | `not null` |
| `source_config_revision` | `text` | `not null` |
| `config_revision` | `text` | `not null`, root agent runtime config revision |
| `status` | `text` | `not null`, enum-like: `draft`, `rendered`, `active`, `superseded`, `failed` |
| `issued_at` | `timestamptz` | `not null` |
| `source_payload_json` | `jsonb` | `not null`, validates `idp.edge.source-config.v1` |
| `created_at` | `timestamptz` | `not null` |

Keys:

- primary key: `(tenant_id, asset_id, agent_id, source_id, source_config_revision)`
- FK: `(tenant_id, asset_id, agent_id, source_id)` -> `sources`
- FK: `(tenant_id, asset_id, agent_id, config_revision)` -> `agent_runtime_config_revisions`
- partial unique index for active source revision: `(tenant_id, asset_id, agent_id, source_id)` where `status = 'active'`

`config_outbox`

| Column | Type draft | Constraints / notes |
| --- | --- | --- |
| `tenant_id` | `text` | `not null` |
| `outbox_id` | `uuid` | `primary key` |
| `idempotency_key` | `text` | `not null unique` |
| `asset_id` | `text` | `not null` |
| `agent_id` | `text` | `not null` |
| `config_revision` | `text` | `not null` |
| `config_scope` | `text` | `not null`, `agent_runtime` или `source:{source_id}` |
| `source_id` | `text` | nullable для `agent_runtime`, `not null` для `source:{source_id}` |
| `source_config_revision` | `text` | nullable для `agent_runtime`, `not null` для source config delivery |
| `message_type` | `text` | `not null`, `idp.edge.config.delivery.v1` |
| `kafka_topic` | `text` | `not null`, default `idp.edge.configs.v1` |
| `kafka_key` | `text` | `not null`, `{tenant_id}|{asset_id}|{agent_id}|{config_scope}` |
| `payload_json` | `jsonb` | `not null`, validates `idp.edge.config.delivery.v1` |
| `status` | `text` | `not null`, `pending`, `inflight`, `published`, `retry`, `dead_letter` |
| `available_at` | `timestamptz` | `not null` |
| `lease_expires_at` | `timestamptz` | nullable |
| `published_at` | `timestamptz` | nullable |
| `attempt_count` | `integer` | `not null default 0` |
| `next_attempt_at` | `timestamptz` | nullable |
| `last_error` | `text` | nullable |
| `created_at` | `timestamptz` | `not null` |
| `updated_at` | `timestamptz` | `not null` |

Keys:

- primary key: `outbox_id`
- unique: `idempotency_key`
- index for reservation: `(status, available_at)`
- index for lease recovery: `(status, lease_expires_at)`
- index: `(tenant_id, asset_id, agent_id, config_revision, config_scope)`
- check: `config_scope = 'agent_runtime'` implies `source_id is null`
- check: `config_scope like 'source:%'` implies `source_id is not null`

Почему отдельные publish job/result таблицы не нужны в MVP:

- `config_outbox.status` отражает состояние доставки конкретного delivery
  record: `pending`, `inflight`, `published`, `retry`, `dead_letter`.
- `lease_expires_at`, `attempt_count`, `next_attempt_at`, `last_error` покрывают
  worker coordination и retry diagnostics.
- `published_at` фиксирует успешную публикацию в Kafka.
- `idempotency_key` и `kafka_key` покрывают идемпотентность и ordered delivery.
- Batch/job-level observability можно строить из `config_outbox` агрегациями; если
  позднее потребуется user-visible publish job lifecycle, это будет отдельный ADR
  и миграция, а не часть текущего baseline.

## Mapping в edge contracts

`idp.edge.agent-runtime-config.v1` строится из:

- `tenants.tenant_id`
- `assets.asset_id`
- `agents.agent_id`
- `agent_runtime_config_revisions.config_revision`
- active `sources.source_id`
- linked `source_config_revisions.source_config_revision`

`idp.edge.source-config.v1` строится из:

- `tenants`
- `assets`
- `agents`
- `sources`
- `points`
- `source_config_revisions`

`idp.source.config.v1` для Kafka строится из того же source config
snapshot и должен сохранять тот же `source_config_revision`.

`idp.edge.config.delivery.v1` является delivery envelope для Kafka topic
`idp.edge.configs.v1`. Он содержит:

- `config_scope`: `agent_runtime` или `source:{source_id}`
- `target_mqtt_topic`
- `mqtt_retain=true`
- `mqtt_qos=1`
- `operation`: `upsert` или `delete`
- `payload_message_type`: `idp.edge.agent-runtime-config.v1` или
  `idp.edge.source-config.v1`
- `payload`: rendered agent runtime/source config для `upsert` или `null` для retained
  delete/tombstone

## Поток доставки конфигурации

PostgreSQL является source of truth для настроек. Kafka является ordered
delivery log для выпусков конфигурации. MQTT retained topics являются delivery
projection для edge-telemetry-agent.

Для связи PostgreSQL и Kafka обязательно реализуется transactional outbox
pattern: изменение configuration state и создание `config_outbox` записи
выполняются в одной PostgreSQL transaction, а отдельный publisher асинхронно
доставляет outbox records в Kafka.

Доставка конфигурации edge-telemetry-agent выполняется по Kafka-first схеме:

```text
Config Registry
  -> PostgreSQL Platform Store
  -> render idp.edge.agent-runtime-config.v1 / idp.edge.source-config.v1
  -> PostgreSQL config_outbox
  -> Config Event Publisher
  -> Kafka idp.edge.configs.v1
  -> Redpanda Connect redpanda input component
  -> MQTT retained topics
  -> Edge Telemetry Agent
```

Edge-agent не читает Kafka напрямую. Он читает только retained MQTT topics.

Платформенные source config snapshots для enrichment, аналитики и ClickHouse
порождаются из того же Kafka delivery log:

```text
Kafka idp.edge.configs.v1
  -> idp.source.configs.v1
  -> source_config_snapshots_v1 в ClickHouse
```

Правила:

- `Config Registry` пишет настройки и rendered config revisions в
  PostgreSQL.
- `Config Registry` не пишет в Kafka напрямую внутри HTTP request.
- `Config Registry` создает transactional `config_outbox` record в той же
  PostgreSQL transaction, где сохраняет rendered config revision.
- `Config Event Publisher` читает `config_outbox`, пишет config delivery record
  `idp.edge.config.delivery.v1` в Kafka topic
  `idp.edge.configs.v1` и помечает outbox record как опубликованный.
- `Redpanda Connect` читает `idp.edge.configs.v1` из Kafka и публикует
  `idp.edge.agent-runtime-config.v1` / `idp.edge.source-config.v1` в retained MQTT
  topics.
- `Source Config Snapshot Projector` читает `idp.edge.configs.v1` и
  публикует canonical `idp.source.config.v1` records в
  `idp.source.configs.v1`.
- Retained MQTT source config topics не являются authoritative ingress path для
  `idp.source.configs.v1`; они только delivery projection для
  edge-telemetry-agent.
- `Edge Telemetry Agent` получает конфигурацию только из retained MQTT topics.
- `Kafka Event Log` является журналом доставки и replay для config revisions,
  но edge не читает Kafka.
- `source_config_revision` должен совпадать в PostgreSQL, retained MQTT payload,
  Kafka `idp.source.config.v1` и ClickHouse
  `source_config_snapshots_v1`.
- Если запись в Kafka успешна, но materialization в MQTT временно не выполнена,
  edge продолжает работать на последней retained config revision.
- Успешная запись в Kafka не равна факту применения конфигурации edge-telemetry-agent-ом.
  Факт применения подтверждается `idp.edge.config.status.v1`.
- Kafka replay должен уметь восстановить retained MQTT config topics после
  потери MQTT broker state.

## Transactional outbox requirements

`config_outbox` является обязательной частью первого backend-инкремента.

Минимальные требования:

- `Config Registry` никогда не пишет в Kafka напрямую из HTTP request.
- Use case, который создает новую `config_revision`, в той же транзакции
  создает `config_outbox` record.
- `config_outbox` record содержит deterministic `event_id` или
  `idempotency_key`.
- Для agent runtime config `idempotency_key`:
  `{tenant_id}|{asset_id}|{agent_id}|{config_revision}|agent_runtime`.
- Для source config `idempotency_key`:
  `{tenant_id}|{asset_id}|{agent_id}|{config_revision}|source|{source_id}`.
- `Config Event Publisher` резервирует outbox records через lease, чтобы
  несколько publisher instances не публиковали одну запись одновременно.
- Outbox statuses: `pending`, `inflight`, `published`, `retry`, `dead_letter`.
- Для `inflight` records должен быть `lease_expires_at`; expired records
  возвращаются в retry/pending flow.
- Publisher должен быть idempotent: повторная публикация одного delivery record
  в Kafka не должна выпускать новую logical config revision.
- Kafka key должен обеспечивать порядок конфигураций для одного agent/source:
  `{tenant_id}|{asset_id}|{agent_id}|{config_scope}`.
- Ошибки публикации сохраняются в `last_error`, `attempt_count` и
  `next_attempt_at`.
- После успешной записи в Kafka publisher помечает outbox record как
  `published` и сохраняет `published_at`.
- Очистка старых published records допускается только после отдельного retention
  policy.

## API surface первого инкремента

Первый API surface ограничивается настройками:

- `GET /health`
- `GET /ready`
- `POST /tenants`
- `GET /tenants`
- `POST /tenants/{tenant_id}/assets`
- `GET /tenants/{tenant_id}/assets`
- `POST /tenants/{tenant_id}/assets/{asset_id}/agents`
- `GET /tenants/{tenant_id}/assets/{asset_id}/agents`
- `POST /tenants/{tenant_id}/assets/{asset_id}/agents/{agent_id}/sources`
- `GET /tenants/{tenant_id}/assets/{asset_id}/agents/{agent_id}/sources`
- `POST /tenants/{tenant_id}/assets/{asset_id}/agents/{agent_id}/sources/{source_id}/points`
- `GET /tenants/{tenant_id}/assets/{asset_id}/agents/{agent_id}/sources/{source_id}/points`
- `POST /tenants/{tenant_id}/assets/{asset_id}/agents/{agent_id}/render-config`
- `GET /tenants/{tenant_id}/assets/{asset_id}/agents/{agent_id}/config-revisions`

Материализация Kafka config delivery records в MQTT retained topics выполняется
  локальным Redpanda Connect pipeline `redpanda-connect-config-projection`.
Первый backend-срез фиксирует Kafka delivery contract, outbox и local
projection, но не хранит timestamp MQTT projection: факт применения
конфигурации edge-telemetry-agent-ом будет приходить отдельно через
`idp.edge.config.status.v1`.

## Рассмотренные варианты

| Вариант | Решение |
| --- | --- |
| Один `Config Registry` на FastAPI | Принят. Дает один понятный backend-срез для хранения настроек без смешения с alarm/auth/frontend. |
| Сразу полный `Platform API` для auth, alarm, telemetry и config | Отклонено. Слишком большой scope, сложно ревьюить и реализовывать последовательно. |
| Микросервисы для tenants/assets/agents/sources/points | Отклонено. Доменная модель еще формируется; раннее дробление усложнит транзакции и миграции. |
| JSONB-only модель настроек | Отклонено. Удобно для быстрого старта, но ломает uniqueness, поиск, миграции и связи с contracts. |
| Полностью нормализованная модель без JSONB | Отклонено для первого инкремента. Protocol-specific connection/policy settings будут быстро меняться. |

## Последствия

Положительные:

- первый backend-срез становится реалистичным и проверяемым
- модель данных прямо следует из edge contracts
- настройки переходят из YAML bundle к PostgreSQL без изменения MQTT wire contracts
- чистая архитектура позволит тестировать use cases без базы и FastAPI
- будущие auth/alarm/frontend ADR не будут тащить за собой уже решенную модель
  хранения настроек

Отрицательные:

- временно нет аутентификации и пользовательских ролей
- API нельзя открывать наружу до отдельного security/auth ADR
- часть protocol-specific данных остается в JSONB и потребует discipline по
  schema validation
- lifecycle/status loop применения config остается отдельным runtime-инкрементом

## План реализации

1. Создать `apps/idp_config_registry`.
2. Добавить зависимости: `fastapi`, `uvicorn`, `pydantic`, `sqlalchemy`,
   `asyncpg`, `alembic`.
3. Создать clean architecture layout: `api`, `application`, `domain`,
   `infrastructure`.
4. Описать domain entities/value objects для tenant/asset/agent/source/point.
5. Описать repository protocols и Unit of Work protocol.
6. Реализовать SQLAlchemy async adapters.
7. Добавить Alembic и первую PostgreSQL migration.
8. Реализовать use cases создания и чтения registry entities.
9. Реализовать render use case для `idp.edge.agent-runtime-config.v1` и
   `idp.edge.source-config.v1`.
10. Добавить `config_outbox` use case для Kafka-first delivery records.
11. Реализовать outbox repository methods: reserve, mark published, mark retry,
    mark dead letter, release expired leases.
12. Добавить tests для use cases на in-memory repository stubs.
13. Добавить integration test для PostgreSQL migrations и basic API.
14. Добавить outbox failure-mode tests: rollback transaction, retry after
    Kafka error, expired lease recovery, duplicate publish idempotency.
15. Добавить local Redpanda Connect projection
    `idp.edge.configs.v1 -> MQTT retained agent runtime/source config topics`
    и integration smoke через MQTT retained readback.

## Проверки принятия

- `Config Registry` не содержит auth/login/JWT/Keycloak кода.
- `Config Registry` не содержит alarm, notification или telemetry read
  endpoints.
- Public/API write operations проходят через application use cases. Internal
  Backoffice CRUD может использовать SQLAdmin ORM shortcut; выпуск новой config
  revision и outbox records всё равно выполняется через render use case.
- Domain/application слои не импортируют FastAPI, SQLAlchemy или asyncpg.
- PostgreSQL таблицы имеют tenant-aware uniqueness constraints.
- Rendered agent runtime/source payloads валидируются по JSON Schema из
  `docs/contracts/edge-telemetry-agent/`.
- Config delivery record сначала попадает в PostgreSQL `config_outbox`, а не
  напрямую в Kafka из HTTP request.
- `config_outbox` реализует transactional outbox pattern: atomic write with
  config revision, lease-based publishing, retry, dead letter и idempotency key.
- Secrets не сохраняются plain text в `connection_json`.
- Public/API hard delete не используется в первом инкременте. Internal
  Backoffice delete допускается только как operator workflow по `ADR-011`.

## Что будет отдельными ADR

- Auth/IAM: Keycloak, JWT, users, roles, tenant claims.
- Platform Frontend и frontend/backend boundary.
- Internal Backoffice Admin UI для Config Registry.
- Alarm Rule Engine и alarm lifecycle.
- Notification Service.
- Streaming Analytics.
- Telemetry read API поверх ClickHouse.
- Config Event Publisher runtime hardening и config projection lifecycle/status.
- API Gateway / reverse proxy / ingress policy.
