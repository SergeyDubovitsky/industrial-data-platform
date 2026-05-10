# ADR-005: `MQTT 5.0` как transport, telemetry events, source config и status topics

Дата: 2026-03-28  
Статус: accepted

## Контекст

Целевой transport для edge agent выбран как `MQTT`, а не `HTTP batch push`. При этом нужно определить:

- как публиковать телеметрию: batch per source или one message per point
- как доставлять source metadata и point registry
- нужен ли отдельный `state` topic
- какие части идентичности хранить в topic, а какие в payload
- как избежать конфликтов с protocol-specific идентификаторами вроде `KNX group address`, содержащими `/`
- как использовать возможности `MQTT 5.0` без лишнего усложнения edge runtime
- как уменьшить число `PUBLISH`, число подписок и размер каждого сообщения

Важные свойства спецификации `MQTT`, которые влияют на решение:

- wildcard-символы допустимы только в topic filters, а не в публикуемом topic name
- порядок сообщений гарантируется для одного topic и QoS на non-shared subscriptions
- retained message хранится на конкретный topic, а не на отдельные элементы внутри batch payload
- `QoS 1` допускает повторную доставку, поэтому transport должен быть совместим с дедупликацией по `event_id`
- `MQTT 5.0` поддерживает `Message Expiry Interval`, `Content Type` и `Topic Alias`, полезные для telemetry transport

## Решение

### 1. Основной transport MVP

Для MVP основным transport принимается `MQTT 5.0`.

- edge agent публикует данные в центральный `MQTT broker`
- локальный `SQLite Delivery Outbox` внутри `Local State Store` остается обязательным буфером и не заменяется broker session state
- publisher не полагается на долгоживущую server-side session для надежности доставки

### 2. Telemetry model

Агент получает source config из retained MQTT topic и публикует telemetry events
и status topics.

- отдельный `state` topic не используется
- текущее состояние точки вычисляется в monitoring backend из последнего валидного события в БД
- retained telemetry state не вводится, чтобы не дублировать state management между broker и backend
- source metadata публикуется не по одной точке, а одним source config record на `source_id`
- per-point retained `meta` topics не используются, чтобы не умножать число retained records и subscriptions

### 3. Гранулярность публикации

Телеметрия публикуется как `one event per point per publish`.

- batch payload на уровень source не используется
- один telemetry event соответствует одному `PUBLISH`
- topic привязан к одной точке, а не к целому источнику
- source config публикуется как один retained record на source, а не как `N` отдельных point metadata records

### 4. Topic tree

Корневой префикс:

- `idp/v1`

Telemetry topic:

- `idp/v1/assets/{asset_id}/agents/{agent_id}/sources/{source_id}/points/{point_key}/event`

Config topics:

- `idp/v1/agents/{agent_id}/config/agent-runtime`
- `idp/v1/agents/{agent_id}/sources/{source_id}/config`

Status topics:

- `idp/v1/agents/{agent_id}/status/config`
- `idp/v1/assets/{asset_id}/agents/{agent_id}/sources/{source_id}/status/connection`
- `idp/v1/assets/{asset_id}/agents/{agent_id}/status/lwt`

Правила:

- `asset_id`, `agent_id`, `source_id` должны соответствовать MQTT-safe path-id contract
- `point_key` не должен использовать raw protocol reference напрямую, если он содержит `/` или другие неудобные символы
- для `point_key` используется обратимо-кодируемое safe representation, например percent-encoding от `point_ref`

### 5. Payload contract

Payload contract зависит от типа topic.

Telemetry payload principles:

- не повторяет `asset_id`
- не повторяет `agent_id`
- не повторяет `source_id`
- не повторяет `point_key`
- не повторяет статические point metadata, которые приходят через retained source config
- содержит только динамические данные события и поля, нужные для дедупликации/диагностики
- содержит `tenant_id` claim из retained agent runtime config
- содержит `source_config_revision`, использованную при формировании события
- для MVP ограничен scalar values: `boolean`, `number`, `string`
- complex protocol values вроде массивов, структур или `ByteString` не входят в текущую версию wire contract

Полная схема telemetry payload является контрактом `idp.edge.telemetry.event.v1` и
зафиксирована в `docs/contracts/edge-telemetry-agent/`.

Source config payload:

- публикуется как retained self-describing record на уровень source
- содержит connection settings, acquisition/publish policies и описание всех точек источника
- позволяет consumer-у сделать одну retained subscription на source вместо `N` per-point metadata subscriptions

Полная схема source config payload является контрактом
`idp.edge.source-config.v1` и зафиксирована в `docs/contracts/edge-telemetry-agent/`.

### 6. QoS и свойства публикации

- telemetry topics: `QoS 1`, `retain = false`
- agent runtime/source config topics: `QoS 1`, `retain = true`
- `Message Expiry Interval` задается конфигом и по умолчанию может быть `86400` секунд
- `Content Type` для JSON payload: `application/json`
- status topics могут использовать `retain = true`
- `lwt` публикуется как retained `offline`, а после успешного connect агент публикует retained `online`
- source config материализуется в retained MQTT topic из Kafka config delivery record при выпуске новой revision
- publisher должен использовать `Topic Alias`, если broker вернул ненулевой `Topic Alias Maximum`, потому что telemetry topics длинные и часто повторяются

### 7. Session policy

Для publisher принимается простая схема:

- `Clean Start = true`
- `Session Expiry Interval = 0`

Надежность доставки обеспечивается локальным outbox и retry policy агента, а не накоплением publisher session state на broker.

### 8. Dedupe и ingestion

- backend обязан считать `event_id` ключом дедупликации
- `event_id` является непрозрачной непустой строкой; backend не должен требовать UUID-only формат
- consumer восстанавливает routing context из topic
- consumer восстанавливает статические point metadata из retained source config по `point_key`
- canonical event в backend может строиться как `topic-derived identity + MQTT payload`

## Обоснование

- per-point event topics лучше соответствуют ordered delivery semantics MQTT
- `retain` бесполезен для batch telemetry и естественно работает только на уровне одного topic
- отсутствие `state` topic убирает дублирование state management между MQTT broker и БД monitoring-сервиса
- один retained source config дает self-describing контракт для внешних MQTT consumer-ов без `N` per-point metadata publishes
- `QoS 1` дает разумный баланс надежности и нагрузки для edge-сценария
- `MQTT 5.0` дает полезные transport properties без необходимости изобретать свои служебные поля
- тонкий telemetry payload уменьшает сетевой overhead на каждое событие
- scalar-only payload keeps KNX/Modbus/most MVP OPC UA cases simple and avoids silent drift into incompatible complex JSON formats

## Последствия

Положительные:

- MQTT становится primary transport уже в MVP
- subscriber может избирательно подписываться по `asset/source/point`
- event stream остается компактным и без дублирования topic identity и стабильной point metadata в payload
- один source config на source уменьшает число retained records и metadata subscriptions
- monitoring backend строит текущее состояние в одном месте, в БД

Отрицательные:

- backend ingestion должен уметь разбирать topic tree
- для protocol-specific `point_ref` нужен стабильный алгоритм построения `point_key`
- consumer-у нужно джойнить event stream с source config, если ему нужны имя, unit или tags
- без retained `state` новый внешний MQTT subscriber не получит текущее значение без участия backend
- future support for complex `OPC UA` values потребует новой версии payload contract

## Source of truth контрактов

Полные MQTT topic templates и payload schemas вынесены в `docs/contracts/edge-telemetry-agent/`.

## Отклоненные альтернативы

- Batch per source topic: хуже для selective subscribe, retained semantics и per-point ordering.
- Отдельный `state` topic в MVP: дублирует state management, хотя monitoring backend уже может считать state из БД.
- Полное дублирование routing identity в payload: увеличивает размер сообщений без необходимости.
- Per-point retained `meta` topics: дают self-describing контракт, но создают лишние retained records и лишнюю нагрузку на consumer discovery.
