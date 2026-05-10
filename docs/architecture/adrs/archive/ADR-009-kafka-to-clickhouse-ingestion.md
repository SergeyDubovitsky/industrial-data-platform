# ADR-009: Путь сохранения данных из Kafka в ClickHouse

Дата: 2026-05-03
Статус: accepted

## Контекст

Текущий `MVP baseline` уже реализует локальный ingestion slice
`MQTT -> Redpanda Connect -> Apache Kafka`. Следующий production-срез должен добавить
долговременное аналитическое хранение в `ClickHouse Telemetry Store`.

Целевой поток платформы остается:

`MQTT -> Redpanda Connect -> Kafka Event Log -> Telemetry Store -> API/Grafana/Analytics`

Source of truth для схем и имен находится в `docs/contracts/`:

- MQTT -> Kafka mapping: `idp.ingestion.mqtt-to-kafka.v1`
- Kafka topics: `idp.kafka.topics.v1`
- ClickHouse storage: `idp.telemetry-store.clickhouse.telemetry-store.v1`

Этот ADR не заменяет contracts. Он выбирает runtime/pattern для доставки Kafka
records в ClickHouse и фиксирует границы реализации до начала разработки
compose, миграций и ingestion runtime.

## Требования и критерии принятия

- Kafka records должны попадать в ClickHouse contract tables без изменения
  `idp.kafka.topics.v1` и `idp.telemetry-store.clickhouse.telemetry-store.v1`.
- `self-hosted` и `cloud` являются deployment modes одной платформы, а не двумя
  разными архитектурами.
- Между deployment modes должны совпадать Kafka topics, ClickHouse table names,
  migration artifacts, connector config shape, DLQ/error semantics и acceptance
  tests.
- Между deployment modes могут различаться только endpoints, credentials,
  TLS/SASL/private networking, resource sizing и managed-service packaging.
- Ошибки connector-а, lag, retries, DLQ и task health должны быть наблюдаемыми.
- Повторная доставка Kafka records не должна ломать UI/API/Grafana запросы.
- Разработка ClickHouse/Kafka ingestion должна следовать этому ADR.

## Решение

Принимается `ClickHouse Kafka Connect Sink` как baseline runtime для пути
`Kafka -> ClickHouse` в `self-hosted` и `cloud` deployment modes.

`ClickHouse Kafka Connect Sink` читает только Kafka topics, где
`telemetry-store-writer.v1` указан как consumer в `idp.kafka.topics.v1`:

- `idp.telemetry.events.v1`
- `idp.source.configs.v1`
- `idp.source.connections.v1`
- `idp.agent.status.v1`
- `idp.derived.events.v1`

`idp.ingestion.errors.v1` не входит в v1 ClickHouse ingestion path:
текущий Kafka contract назначает его для operations tooling. Если ingestion
errors нужно хранить в ClickHouse, для этого требуется отдельный storage
contract и миграция.

Kafka Connect Sink пишет records в ClickHouse landing tables. Для
несовпадающих topic/table names используется `topic2TableMap`.

Canonical transform выполняется в ClickHouse через materialized views:

- Kafka Connect Sink пишет только в landing tables.
- Materialized views являются единственным владельцем преобразования landing
  rows в `idp.telemetry-store.clickhouse.telemetry-store.v1`.
- Kafka Connect SMT не используется для доменного mapping в v1. Он допускается
  только для технических преобразований connector-а, например сохранения Kafka
  key/header metadata в landing columns.
- Отдельный stream processor не входит в v1 Kafka -> ClickHouse path.

Landing tables создаются заранее миграциями ClickHouse. Для v1 выбирается
универсальная raw landing model: по одной landing table на Kafka topic, с
сырой JSON/String payload column. Landing tables не пытаются
колонка-в-колонку повторять polymorphic Kafka payload.

Минимальный shape первой миграции landing tables:

- `payload_json String`
- `ingested_at DateTime64(3, 'UTC')`

Kafka metadata columns (`topic`, `partition`, `offset`, `key`, `timestamp`)
являются follow-up расширением landing schema. Их можно добавить только после
PoC, который подтвердит, что `ClickHouse Kafka Connect Sink` с
`StringConverter` и/или supported SMT надежно заполняет metadata без unsafe
domain mapping в connector config.

Materialized views парсят `payload_json`, раскладывают Kafka payload fields и
пишут в contract tables:

- `telemetry_events_v1`
- `source_config_snapshots_v1`
- `source_connection_events_v1`
- `agent_status_events_v1`
- `derived_events_v1`

`alarm_history_events_v1` не наполняется этим Kafka Connect path в v1. Текущий
ClickHouse contract назначает writer `alarm-rule-engine.v1`, а Kafka contract
не содержит alarm-history topic. Эта таблица создается миграциями как часть
core storage contract, но ее write path должен быть определен отдельно в
контексте `Alarm Rule Engine`.

Для telemetry и derived events polymorphic Kafka field `value` раскладывается в
typed ClickHouse columns:

- `value_type = "number"` -> `value_float`
- `value_type = "boolean"` -> `value_bool`
- `value_type = "string"` -> `value_string`
- `value_raw`, `metadata`, `attributes` и payload-like fields сохраняются как
  JSON/String columns согласно storage contract

Rollups/latest tables (`telemetry_1m_v1`, `telemetry_1h_v1`,
`telemetry_latest_v1`) не входят в первую миграцию. Их нужно проектировать после
PoC запросов API/Grafana и отдельно зафиксировать миграцией.

## Delivery и дедупликация

MVP использует at-least-once delivery. Это означает, что Kafka record может быть
доставлен в ClickHouse больше одного раза после retry/restart.

Для telemetry и derived events дедупликация выполняется на contract tables через
`idempotency_key` и `ReplacingMergeTree`, как описано в
`idp.telemetry-store.clickhouse.telemetry-store.v1`.

Правила чтения:

- Raw/history tables являются append/dedup storage layer, а не прямым UI state
  API.
- Запросы, которым нужна логически дедуплицированная история до фоновых merge
  процессов ClickHouse, должны использовать `FINAL` или отдельные
  deduplicated/query views.
- UI/API для "текущего состояния" не должны читать `telemetry_events_v1`
  напрямую; для этого позже добавляется `telemetry_latest_v1` или
  эквивалентный latest-state view.
- Grafana/API запросы по агрегатам должны переходить на rollup tables после
  появления `telemetry_1m_v1` и `telemetry_1h_v1`.
- Для service history tables без `idempotency_key` возможные at-least-once
  дубли считаются допустимыми в MVP для operational history. Если service
  history станет billing/audit-critical, нужно добавить deterministic event key
  в contract v2 или включить проверенный exactly-once path.

`exactlyOnce=true` в ClickHouse Kafka Connect Sink не включается по умолчанию.
Его можно принять позже только после failure-mode PoC для сценариев:

- ClickHouse insert успешен, но connector падает до offset commit.
- Kafka Connect task перезапускается или rebalance-ится.
- ClickHouse временно недоступен.
- KeeperMap/state-store расходится с Kafka offsets.

## Kafka Connect operational scope

Выбор Kafka Connect означает, что ingestion runtime становится
эксплуатационным компонентом платформы.

Минимальные требования для production:

- Kafka Connect запускается в distributed mode.
- Internal topics `config.storage.topic`, `offset.storage.topic` и
  `status.storage.topic` создаются явно, compacted и с production replication
  factor в production broker-е.
- Connector config хранится как versioned JSON/YAML artifact рядом с
  infra/config. В distributed mode этот artifact применяется автоматизированным
  deploy/bootstrap шагом через Kafka Connect REST API. Ручные изменения через
  UI/API считаются configuration drift и должны перезатираться или
  блокироваться operational policy.
- Secrets для Kafka и ClickHouse не хранятся в connector config в открытом виде;
  используются secret store/env injection в зависимости от deployment mode.
- Kafka auth/TLS/SASL и ClickHouse TLS настраиваются как обязательная часть
  production profile.
- Kafka Connect REST API доступен только trusted operations plane, не публичным
  пользователям.
- JMX/metrics собираются в observability stack; минимум отслеживаются task
  status, consumer lag, retries, DLQ records, insert latency и ClickHouse errors.
- Upgrade connector-а выполняется как platform operation с проверкой migration
  compatibility и rollback plan.

## Cloud и self-hosted parity

`ClickHouse Kafka Connect Sink` выбран как общий baseline, потому что он
доступен и для self-hosted, и для cloud deployments.

Cloud-specific ingestion, например managed `ClickPipes`, не выбирается как
default path. Он может снизить операционную нагрузку в ClickHouse Cloud, но
создает риск отдельной cloud-only архитектуры.

`ClickPipes` можно пересмотреть позже только как managed optimization, если
сохраняются:

- те же Kafka topics и value schemas
- те же ClickHouse contract tables и migrations
- те же landing/transform semantics или полностью совместимый результат
- те же DLQ/error semantics
- те же acceptance tests для `Kafka -> ClickHouse`

## Сравнение вариантов

| Вариант | Плюсы | Минусы / риски | Решение |
| --- | --- | --- | --- |
| `ClickHouse Kafka Connect Sink` | Официальный ClickHouse connector; Kafka Connect operational model; DLQ, retries, JMX metrics; JSON/Avro/Protobuf; может работать с exactly-once; масштабируется через `tasks.max`; применим в cloud и self-hosted | Нужен Kafka Connect service; target tables должны существовать заранее; нужны landing tables и `topic2TableMap`; exactly-once требует state-store и отдельной проверки; buffering несовместим с exactly-once | Preferred baseline для v1 |
| `ClickHouse Kafka engine + Materialized View` | Встроен в OSS ClickHouse; простой локальный старт; меньше сервисов | At-least-once; слабее error/debug handling; consumer масштабируется вместе с ClickHouse, а не отдельно; ClickHouse должен напрямую ходить в Kafka | Fallback/PoC option |
| Custom `telemetry-store-writer` на Python | Полный контроль над domain validation, JSON schema validation, offset commit, typed value mapping и error model | Нужно самим реализовать batching, retries, lag metrics, offset safety, backpressure и эксплуатацию | Fallback, если Kafka Connect Sink не пройдет PoC |
| `Redpanda Connect sql_insert` | Уже используется Redpanda Connect; декларативный pipeline; batching; ClickHouse driver | Generic SQL sink, меньше first-class ClickHouse semantics; сложная domain mapping логика уйдет в Bloblang/SQL config; нет преимущества над официальным ClickHouse sink | Не выбирать для durable Telemetry Store path |
| Managed `ClickPipes` | Нативный managed ingestion в ClickHouse Cloud; меньше операционной нагрузки в cloud; поддерживает Kafka-compatible sources | Не является одинаковым self-hosted path; может создать отдельную cloud-only архитектуру, отличающиеся настройки, мониторинг и failure semantics | Не выбирать как baseline; пересматривать только как optimization без изменения контрактов |

## Последствия

Положительные:

- используется официальный ClickHouse-supported путь для Kafka ingestion
- cloud и self-hosted deployment modes используют один baseline ingestion pattern
- меньше собственного кода ingestion runtime
- Kafka Connect дает стандартный REST/JMX operational surface
- есть готовые механизмы retry, DLQ и task status
- transform ownership зафиксирован в ClickHouse materialized views

Отрицательные:

- локальный compose становится тяжелее: добавляется Kafka Connect service
- нужно управлять Kafka Connect internal topics и connector lifecycle
- нужно поддерживать connector config как production artifact
- нужен явный landing layer между Kafka records и ClickHouse contract tables
- raw/history reads должны учитывать eventual merge/dedup поведение ClickHouse
- managed cloud сохраняет Kafka Connect как управляемый нами компонент, даже
  если у ClickHouse Cloud есть более managed-native ingestion options

## План внедрения

1. Добавить ClickHouse в `infra/local/compose.yaml`.
2. Добавить Kafka Connect service с установленным ClickHouse Kafka Connect Sink.
3. Создать Kafka Connect internal topics в local/prod profiles.
4. Настроить миграционный workflow ClickHouse.
5. Создать первую миграцию core contract tables и raw JSON/String landing tables.
6. Добавить materialized views для landing -> contract transform без
   `alarm_history_events_v1`.
7. Добавить connector config с `topic2TableMap`, DLQ, retry policy, metrics и
   secret injection.
8. Добавить integration test:
   `edge_telemetry_agent -> MQTT -> Kafka -> Kafka Connect Sink -> ClickHouse landing -> contract table`.
9. Добавить dedup/read verification для повторной доставки одного telemetry
   record.

## Implementation notes

Первая локальная реализация использует Confluent Hub package
`clickhouse/clickhouse-kafka-connect` и Confluent Platform Kafka Connect image
`confluentinc/cp-kafka-connect:7.7.1`. Для local MVP
`CLICKHOUSE_KAFKA_CONNECT_VERSION` временно равен `latest`: текущий Confluent
Hub client успешно резолвит `latest` в ClickHouse connector `v1.3.7`, но
отклоняет явный version string. Production/self-hosted profile должен заменить
это на pinned artifact/download step до release hardening.

Raw landing PoC path зафиксирован следующими настройками connector-а:

- `key.converter=org.apache.kafka.connect.storage.StringConverter`
- `value.converter=org.apache.kafka.connect.storage.StringConverter`
- `transforms=HoistValue`
- `transforms.HoistValue.type=org.apache.kafka.connect.transforms.HoistField$Value`
- `transforms.HoistValue.field=payload_json`
- `exactlyOnce=false`
- `errors.tolerance=all`
- `errors.deadletterqueue.topic.name=idp.telemetry-store.dlq.v1`

Landing tables пока содержат только `payload_json String` и
`ingested_at DateTime64(3, 'UTC') DEFAULT now64(3)`. Kafka metadata columns
остаются follow-up расширением до отдельного подтверждения metadata capture.

Вторая локальная миграция добавляет materialized views для
`telemetry`, `source config`, `source connection`, `agent status` и
`derived events`. MV layer выполняет fail-fast проверку обязательных полей
через ClickHouse `throwIf`; невалидный raw record не создает corrupt contract
row и попадает в Kafka Connect DLQ
`idp.telemetry-store.dlq.v1`.

## Что пересмотреть позже

- включать ли `exactlyOnce=true` после failure-mode PoC
- нужны ли отдельные connector instances на high-volume topics
- нужен ли отдельный stream processor, если ClickHouse materialized views станут
  слишком сложным местом для transform logic
- когда добавлять rollups/latest tables
- нужен ли managed ClickHouse/ClickPipes путь для cloud deployment как
  optimization, если он не создает расхождение с self-hosted contract path

## Источники

- [ClickHouse: Integrating Kafka with ClickHouse](https://clickhouse.com/docs/integrations/kafka)
- [ClickHouse Kafka Connect Sink](https://clickhouse.com/docs/integrations/kafka/clickhouse-kafka-connect-sink)
- [ClickHouse Kafka table engine](https://clickhouse.com/docs/engines/table-engines/integrations/kafka)
- [Apache Kafka Connect User Guide](https://kafka.apache.org/35/kafka-connect/user-guide/)
