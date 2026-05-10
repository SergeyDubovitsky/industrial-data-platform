# Архитектура универсального решения для промышленного сбора и мониторинга

Дата: 2026-05-10
Статус: working draft

## Назначение

Цель решения: развернуть на объекте `Edge Telemetry Agent`, который подключается
к полевым протоколам и локальным системам автоматизации, получает телеметрию,
нормализует значения, фильтрует шум, буферизует события при недоступности
внешнего контура и отправляет данные в `Industrial Data Platform` в
`self-hosted` инсталляции или в облаке/интернете.

Целевой контур должен поддерживать не только `KNX`, но и `OPC UA`, `Modbus`, а
также другие PLC/SCADA-интеграции через southbound-адаптеры. Следующий
выбранный post-MVP protocol track после `KNX` — `OPC UA read-only ingestion`:
`edge_telemetry_agent` работает как `OPC UA client` и только считывает данные из
`OPC UA server`.

Текущий практический фокус проекта: демо-стенд `KNX` как первый реализуемый адаптер и MVP без управляющих действий в production data path.

Проект уже достиг `MVP baseline`: текущий реализованный baseline включает
`Edge Telemetry Agent`, retained agent runtime/source config path и local platform
slice `MQTT -> Redpanda Connect -> Apache Kafka`. Более широкая platform-часть ниже в
документе остается целевой post-MVP эволюцией.

Поверх этого baseline в текущей ветке уже реализованы первые локальные
data-platform foundation slices: `Config Registry` на `PostgreSQL`, Kafka-first
config delivery projection, `ClickHouse Telemetry Store` path и `Grafana`
read-model surface как первый `Web Monitoring Module` surface.

Первый post-MVP пилот запускается cloud-first в российском облаке (`VK Cloud`
или `Yandex Cloud`). On-prem/self-hosted остается целевым deployment mode
продукта, но не является target первого пилота.

## Границы решения

В контуре этого решения:

- `Edge Telemetry Agent`, разворачиваемый непосредственно на объекте
- `Industrial Data Platform`, разворачиваемая как `self-hosted` инсталляция или в облаке/интернете
- `Web Monitoring Module`, отдельный модуль dashboards/history/read UI поверх data platform
- `Alarm Management Module`, отдельный модуль правил, lifecycle и notifications поверх data platform
- подключение к полевым шлюзам, контроллерам и промышленным интерфейсам в локальной сети объекта
- сбор входящих событий и выборочное чтение известных тегов/адресов/регистров
- декодирование полезной нагрузки по известной протокольной модели
- нормализация в единый формат событий
- фильтрация событий по правилам `change_threshold`
- локальный буфер исходящих сообщений
- доставка событий в `Industrial Data Platform` по `MQTT 5.0`
- централизованное хранение телеметрии, service events, source config snapshots,
  derived events и storage sink для истории `alarm`
- операторские панели мониторинга в `Web Monitoring Module`
- `alarm`-логика и маршрутизация уведомлений в `Alarm Management Module`
- эксплуатационные логи, health-события и базовые метрики

Вне контура:

- автоматическое и полное discovery всех сущностей, тегов и моделей данных без исходной карты адресов
- бизнес-логика управления оборудованием
- управляющие команды из Web Monitoring UI/API
- долгосрочное хранение телеметрии на edge-узле
- полноценная SCADA/HMI для управляющего контура
- расширенная аналитика и отчетность вне базового data-platform и module scope
- реализация всех protocol-specific security modes в MVP
- внешние провайдеры доставки email/SMS/push/webhook

## Системный контекст

Source of truth для `C1/C2` и следующих уровней декомпозиции находится только в LikeC4-модели в `arch/likec4/`.

Актуальные представления:

- `C1`: `arch/likec4/views.c4` -> `c1-system-context`
- `C2`: `arch/likec4/systems/edge-telemetry-agent/views.c4` -> `c2-edge-telemetry-agent-containers`
- `C2`: `arch/likec4/systems/industrial-data-platform/views.c4` -> `c2-industrial-data-platform-containers`
- `C2`: `arch/likec4/systems/web-monitoring-module/views.c4` -> `c2-web-monitoring-module-containers`
- `C2`: `arch/likec4/systems/alarm-management-module/views.c4` -> `c2-alarm-management-module-containers`

Ключевые внешние взаимодействия:

- `Service engineer` взаимодействует с `Edge Telemetry Agent`, `Industrial Data Platform`, `Web Monitoring Module` и `Alarm Management Module`.
- `Edge Telemetry Agent` работает в локальной сети объекта рядом с источниками данных.
- `Industrial Data Platform` принимает события от edge-агентов и работает как центральное ядро сбора/хранения данных в `self-hosted` инсталляции или в облаке/интернете.
- `Operator` работает через `Web Monitoring Module` и, если разрешено ролью, через `Alarm Management Module`.
- `Dispatcher` работает через `Alarm Management Module` и диспетчерские monitoring screens.
- `Notification channels` остаются внешней системой относительно `Alarm Management Module`.

## Основные архитектурные принципы

- Edge-first. Сборщик работает в сети объекта и не зависит от постоянной доступности внешнего контура.
- Read-only by default. В production data path data-platform контура сервис
  читает и наблюдает сигналы, но не отправляет управляющие команды из web UI/API.
- Server-issued config. Все известные точки, `value_model`, параметры чтения и правила публикации приходят в edge-telemetry-agent как retained agent runtime/source configs; целевой поток доставки: PostgreSQL config revisions -> config outbox -> Kafka -> Redpanda Connect -> MQTT retained topics.
- Hybrid acquisition. Основной поток данных приходит из event/listen режима там, где он поддерживается; активное чтение включается только для whitelist endpoints.
- Loose coupling. Протокольная интеграция, правила фильтрации и доставка во внешний контур разделены по компонентам.
- Fail-safe degradation. При потере backend события не теряются сразу, а уходят в локальный Delivery Outbox.
- Deployment parity. `self-hosted` и `cloud` рассматриваются как два deployment mode одной `Industrial Data Platform` с модулями поверх нее; baseline contracts, основной data path и operational model должны оставаться максимально одинаковыми.
- Cloud-first pilot. Первый пилот идет в российском облаке; self-hosted/on-prem
  не должен получать отдельную архитектуру и возвращается как deployment mode
  после cloud validation.
- Local Docker as product infrastructure. Локальный `Docker Compose` stack
  обязателен для разработки, integration/smoke тестов, onboarding и
  воспроизведения проблем.

## Функциональные требования

- принимать входящие данные через southbound-адаптеры, включая `KNX`,
  `OPC UA` read-only ingestion, future `Modbus` и другие источники
- выполнять `read_on_start` для явно разрешенных status/sensor endpoints
- поддерживать периодическое чтение только для отдельных endpoints
- различать `command`, `feedback`, `status`, `sensor`
- публиковать дискретные сигналы по изменению состояния
- публиковать аналоговые сигналы по достижению порога изменения
- логировать события связи, декодирования и доставки
- буферизовать неотправленные события локально
- принимать `MQTT` telemetry events и status topics в `Industrial Data Platform`; retained agent runtime/source configs являются delivery projection для edge-telemetry-agent
- хранить телеметрию, source config snapshots, service history, derived events и storage sink для истории `alarm`
- предоставлять read models и registry/config metadata прикладным модулям
- выполнять правила `alarm` и маршрутизировать уведомления в отдельном `Alarm Management Module`
- предоставлять dashboards/history/operator read UI в отдельном `Web Monitoring Module`

## Нефункциональные требования

- развертывание edge runtime на отдельном узле или управляемом runtime рядом с
  локальными источниками данных
- работа без локального edge broker на объекте
- восстановление после кратковременной потери сети и southbound-соединения
- предсказуемое поведение после перезапуска за счет `read_on_start`, SQLite Point State Cache и Delivery Outbox
- локальный `docker compose` stack как обязательный dev/test baseline
- production launcher для edge runtime уточняется отдельно; `systemd`-обертка
  остается возможным hardening-вариантом
- `MQTT 5.0` как primary transport MVP без переписывания ядра сбора

## Логическая архитектура

Контейнерные схемы логической архитектуры ведутся только в LikeC4.

На уровне `C2` сейчас зафиксированы:

- `Edge Telemetry Agent`: `Bootstrap Configuration`, `Collector Runtime`, `Local State Store`, `Delivery Worker`
- `Industrial Data Platform`: `MQTT Ingestion Gateway`, `Redpanda Connect`, `Kafka-compatible Broker Runtime`, `Kafka Event Log`, `Source Config Snapshot Projector`, `Telemetry Store Writer`, `Streaming Analytics`, `Telemetry Store`, `Platform Store`, `Config Registry`, `Keycloak`
- `Web Monitoring Module`: `Grafana`, future `Web Monitoring Frontend`
- `Alarm Management Module`: `Alarm Rule Engine`, `Notification Service`

### Поток данных в Industrial Data Platform

Целевой production-поток следующего этапа поверх текущего `MVP`:

1. `Config Registry` хранит rendered agent runtime/source config revisions в PostgreSQL и создает `config_outbox` record.
2. `Config Event Publisher` публикует `idp.edge.config.delivery.v1` records в Kafka topic `idp.edge.configs.v1`.
3. `Redpanda Connect` материализует config delivery records в retained MQTT agent runtime/source topics; edge-telemetry-agent получает `tenant_id`, `asset_id`, `sources` и `points` из этих retained configs.
4. `Source Config Snapshot Projector` строит `idp.source.configs.v1` из `idp.edge.configs.v1`; retained MQTT source configs не являются authoritative Kafka ingress для source config snapshots.
5. `Edge Telemetry Agent` в текущем runtime baseline публикует telemetry events по `MQTT 5.0`; source connection status, config status и agent LWT/status остаются target contracts следующей runtime-фазы.
6. `MQTT Ingestion Gateway` принимает MQTT-поток, валидирует payload и восстанавливает routing context.
7. `Redpanda Connect` подписывается на MQTT topics через `mqtt` input.
8. `Redpanda Connect` применяет mapping/transform pipeline по контракту `idp.ingestion.mqtt-to-kafka.v1`, валидирует `tenant_id` claim и пишет canonical records в Kafka-compatible broker через `redpanda` output component.
9. `Kafka-compatible Broker Runtime` хранит и обслуживает `Kafka Event Log` по контракту `idp.kafka.topics.v1`. Локальный MVP использует `Apache Kafka`; `Redpanda broker` остается candidate после отдельного compatibility PoC.
10. `Telemetry Store Writer` / Kafka Connect читают Kafka topics и записывают raw/canonical telemetry events, source config snapshots, source connection history и agent status history в `Telemetry Store` на базе `ClickHouse` по контракту `idp.telemetry-store.clickhouse.telemetry-store.v1`.
11. `Streaming Analytics` читает Kafka topics, при необходимости читает исторический контекст из `Telemetry Store`, рассчитывает агрегаты и производные признаки, записывает результаты в `Telemetry Store` и публикует derived events для прикладных модулей.
12. `Web Monitoring Module` читает dashboards/history/latest read models из `Telemetry Store` и registry/config metadata из data-platform backend.
13. `Alarm Management Module` читает telemetry/status/derived streams, обрабатывает правила, пишет immutable alarm history в `Telemetry Store`, хранит current alarm state и operator workflow state в `Platform Store` на базе `PostgreSQL` и инициирует уведомления.

### Хранилища данных Industrial Data Platform

Активное решение по persistence кратко зафиксировано в
`docs/architecture/decisions.md`; contract-level детали находятся в
`docs/contracts/`.

- `Telemetry Store` — `ClickHouse`, authoritative analytical store для append-only telemetry events, source config snapshots, source connection history, agent status history, derived events, aggregates, rollups и immutable alarm history. `alarm_history_events_v1` остается storage sink, но writer/owner потока находится в `Alarm Management Module`.
- `Platform Store` — `PostgreSQL`, transactional store для assets, agents, sources, point registry, shared platform state, module workflow state, audit и Keycloak persistence.
- `Kafka-compatible Broker Runtime` и `Kafka Event Log` являются streaming/replay слоем и не заменяют долговременное хранилище платформы.

Source of truth для ingestion, Kafka topics, ClickHouse contracts и migrations
находится в
`docs/contracts/platform-ingestion/`, `docs/contracts/kafka/` и
`docs/contracts/clickhouse/`.

## Компоненты и ответственность

| Компонент | Ответственность |
| --- | --- |
| `Bootstrap Config Loader` | Загружает минимальную локальную конфигурацию запуска: `agent_id`, MQTT endpoint, credentials/secret refs, local storage и observability |
| `Retained Config Loader` | Получает `idp.edge.agent-runtime-config.v1` и `idp.edge.source-config.v1` из MQTT, валидирует revision и собирает agent runtime config |
| `Southbound Connection Manager` | Устанавливает протокольные соединения, отслеживает состояние каналов, выполняет reconnect |
| `Protocol Event Listener` | Получает входящие события, выделяет endpoint, направление и raw payload |
| `Selective Read Scheduler` | Выполняет `read_on_start` и `periodic_read` только по whitelist endpoints |
| `Protocol Decoder / Normalizer` | Преобразует raw payload в типизированное значение по протокольной модели |
| `In-memory Last Value Cache` | Хранит последнее увиденное и последнее отправленное значение по каждой точке во время работы процесса |
| `SQLite Point State Cache` | Сохраняет последнее состояние точки, sequence и контекст фильтрации для warm restart |
| `Change Filter` | Решает, публиковать событие или подавить его как дубль/шум |
| `SQLite Delivery Outbox` | Временно хранит telemetry events, ожидающие доставки или повторной отправки |
| `MQTT Publisher` | Публикует telemetry events с `tenant_id` claim в broker, ведет retry и отмечает статус доставки; config/operational status topics остаются target contracts следующей runtime-фазы |
| `Logs / Metrics / Health` | Пишет эксплуатационные события и дает наблюдаемость по сервису |

## Развертывание

### Целевая production-топология

- один edge-узел в той же L2/L3-сети, что и полевые шлюзы/контроллеры
- `Edge Telemetry Agent` работает на этом узле как локальный edge runtime
- `Industrial Data Platform` работает как центральное ядро в `self-hosted` инсталляции или в облаке/интернете
- `Web Monitoring Module` и `Alarm Management Module` разворачиваются поверх того же data-platform baseline
- первый post-MVP пилот `Industrial Data Platform` работает cloud-first в российском
  облаке (`VK Cloud` или `Yandex Cloud`)
- on-prem/self-hosted deployment не входит в первый пилот, но остается целевым
  mode после cloud validation
- локальный `docker compose` stack остается обязательным dev/test baseline
- конфиги монтируются read-only
- `SQLite Local State Store` хранится на локальном диске edge-узла
- наружу открыт только исходящий `MQTT/TLS` к data-platform ingestion broker
- входящие публичные порты на edge-узле не требуются, кроме опционального health/metrics в локальном сегменте

### Deployment modes Industrial Data Platform

- `cloud-first pilot`: первый пилот разворачивается в `VK Cloud` или
  `Yandex Cloud`; provider-specific детали не должны менять contracts, topics,
  schemas, migrations или acceptance tests.
- `self-hosted`: платформа разворачивается в инфраструктуре заказчика или в
  управляемом нами isolated environment, но использует те же contracts,
  ingestion pattern и storage boundaries.
- `cloud`: платформа разворачивается в публичном или managed cloud, но не
  должна получать отдельную cloud-only архитектуру как baseline.
- Допустимы platform-managed оптимизации для одного из deployment modes только
  если они не меняют MQTT/Kafka/ClickHouse contracts, acceptance tests и
  операционную семантику основного data path.

### Текущий demo-стенд

- для demo-стенда текущий runtime `Edge Telemetry Agent` запускается не на объекте, а на удаленном `Developer Workstation`
- доступ к стенду выполняется через whitelisted public endpoint `${KNX_EXTERNAL_GATEWAY_IP}:${KNX_EXTERNAL_GATEWAY_PORT}`
- NAT-маршрут: `${KNX_EXTERNAL_GATEWAY_IP}:${KNX_EXTERNAL_GATEWAY_PORT} -> ${KNX_LOCAL_GATEWAY_IP}:${KNX_LOCAL_GATEWAY_PORT}`
- на том же рабочем месте текущая реализация поднимает локальный `MQTT broker`
- этот режим используется только для integration-проверки первого `KNX`-адаптера
- он не считается целевой production-схемой
- versioned edge profile для этого сценария должен использовать отдельный remote-profile, а не production-like local-on-site profile

### Web Monitoring в MVP и production

`Grafana` рассматривается как первый реализованный surface
`Web Monitoring Module` и остается в production-контуре как read-only слой
визуализации поверх data platform.

В целевом production-контуре `Grafana` читает подготовленные данные из
`Telemetry Store` на базе `ClickHouse`, а не является consumer-ом исходного MQTT-потока.

Ограничения текущего MVP-среза:

- локальный demo/integration flow ограничен `KNX -> edge_telemetry_agent -> MQTT`
- Grafana не входит в текущий обязательный demo surface
- alarm-логика, история и richer backend-возможности принадлежат отдельному
  `Alarm Management Module`; data platform предоставляет storage/event-log
  boundary для этих записей

## Основные runtime-сценарии

### 1. Холодный старт

1. Сервис загружает `edge.bootstrap-config.v1`.
2. Подключается к MQTT broker и подписывается на retained agent runtime/source config topics.
3. Получает `idp.edge.agent-runtime-config.v1`, затем `idp.edge.source-config.v1` для каждого активного `source_id`.
4. Валидирует `tenant_id`, `asset_id`, `config_revision` и `source_config_revision`; публикация `status/config` остается target contract следующей runtime-фазы.
5. Поднимает southbound-соединение для активных адаптеров.
6. Выполняет `read_on_start` по разрешенным endpoints.
7. Запускает пассивное прослушивание и фоновую публикацию Delivery Outbox в `MQTT`.
8. Публикация retained operational status topics остается target contract следующей runtime-фазы.

### 2. Нормальная работа

1. Сервис получает событие или значение из southbound-адаптера.
2. Находит конфигурацию endpoint.
3. Декодирует значение по протокольной модели.
4. Сравнивает с last value cache, SQLite Point State Cache и правилами публикации.
5. Если событие значимо, обновляет локальный state, кладет событие в SQLite Delivery Outbox и публикует наружу как отдельный `MQTT` event.

### 3. Backend недоступен

1. `MQTT publisher` получает ошибку отправки.
2. Событие остается в `SQLite Delivery Outbox`.
3. Доставка повторяется с backoff.
4. Сервис продолжает сбор телеметрии без остановки.

### 4. Потеря southbound-связи

1. Connection manager фиксирует `connection_lost`.
2. Listener прекращает получать входящие события.
3. Запускается reconnect policy.
4. После восстановления выполняется повторный `read_on_start` для критичных status/sensor endpoints.

## Модель данных на границе домена

Нормализованное событие должно содержать минимум:

- `ts`
- `event_id`
- `tenant_id`
- `agent_id`
- `asset_id`
- `source_id`
- `source_type`
- `point_ref`
- `name`
- `value_type`
- `value_model`
- `signal_type`
- `observation_mode`
- `value`
- `value_raw`
- `quality`

Подробный контракт вынесен в `docs/contracts/edge-telemetry-agent/`.

## MQTT status topics и operational logs

Во внешний контур публикуются только те status topics, которые зафиксированы
transport-контрактом в
`docs/contracts/edge-telemetry-agent/mqtt-topic-tree.v1.md`:

- `idp/v1/assets/{asset_id}/agents/{agent_id}/sources/{source_id}/status/connection`
- `idp/v1/assets/{asset_id}/agents/{agent_id}/status/lwt`

Во внутренних operational logs дополнительно полезны:

- `reconnect_started`
- `reconnect_succeeded`
- `point_read_sent`
- `event_suppressed`
- `decode_failed`

## Безопасность

Для MVP принимаются следующие правила:

- сервис располагается в локальной сети объекта, рядом с полевыми шлюзами и контроллерами
- прямой внешний доступ к промышленным southbound-интерфейсам не используется как штатный production-сценарий
- в проде запрещены управляющие команды из Web Monitoring UI/API
- запрет на управляющие команды не относится к техническим platform writes:
  telemetry/status storage, config revisions, outbox, audit и alarm workflow
  state
- если для отдельного проекта вводится внешний `OPC`-мост с write-path в `KNX`, он должен рассматриваться как отдельный сервис вне текущего data-platform и Web Monitoring контуров
- токены/секреты доставки не хранятся plain text в retained source config или YAML config bundle, а передаются через secret refs или отдельный защищенный secret flow

Целевой roadmap безопасности:

- переход на защищенные режимы конкретных протоколов там, где это поддерживается проектом
- взаимная аутентификация между edge-сервисом и backend
- контроль целостности конфигурации и журналирование изменений

## Риски и ограничения

- без исходной карты тегов, регистров и моделей данных нельзя гарантированно восстановить полную семантику сигналов
- часть источников может поддерживать только polling, а часть только event-driven обновления
- если протокольная модель значения неизвестна, корректная production-нормализация невозможна
- `SQLite` на edge-узле является локальным техническим state store для cache/outbox, а не источником истины состояния оборудования и не архивом телеметрии

## Этапы развития

### Этап 1. MVP

- прямое подключение через первый southbound-адаптер
- listen/poll + `read_on_start`
- структурированный лог
- `SQLite Local State Store`: Point State Cache и Delivery Outbox
- `MQTT 5.0` transport для retained agent runtime/source configs, telemetry events и status topics

### Этап 2. Production hardening

- полноценный delivery worker
- мониторинг lag Delivery Outbox и качества доставки
- health endpoints и metrics
- нормальный lifecycle `reconnect + re-read`

### Этап 3. Масштабирование

- несколько протокольных сегментов/сайтов
- централизованная схема конфигурации
- optional `HTTP` sink или дополнительные transports без изменения доменной модели
- опциональные специализированные брокеры/шлюзы, если появятся несколько параллельных локальных потребителей

## Связанные артефакты

- `arch/README.md`
- `docs/architecture/glossary.md`
- `docs/contracts/README.md`
- `docs/contracts/edge-telemetry-agent/`
- `apps/edge_telemetry_agent/docs/data-contracts.md`
- `apps/edge_telemetry_agent/docs/mqtt-topics.md`
- `docs/architecture/open-questions.md`
- `docs/architecture/decisions.md`
- `docs/architecture/adrs/archive/`
- `docs/contracts/edge-telemetry-agent/config-bundle.v1.md`
