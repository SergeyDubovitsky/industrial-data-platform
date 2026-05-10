# Глоссарий архитектуры

Дата: 2026-05-10
Статус: working draft

Канонический словарь терминов проекта хранится в этом документе.
LikeC4-модель в `arch/likec4/` и markdown-документы в `docs/architecture/`
должны использовать именно эти термины, если нет отдельной оговорки.

## Основные системы

- `Edge Telemetry Agent` — продуктово-архитектурное имя периферийной системы; текущий реализованный модуль в коде — `apps/edge_telemetry_agent` / package `edge_telemetry_agent`.
- `Industrial Data Platform` — центральное ядро системы сбора и хранения данных: принимает события от edge agents, ведет Kafka-compatible event log, хранит telemetry/service history, управляет config registry и предоставляет read/storage boundaries для прикладных модулей.
- `Web Monitoring Module` — отдельный прикладной модуль поверх `Industrial Data Platform`: dashboards, history views, latest values, operator read screens и read-only visualization. Текущий `Grafana` surface относится сюда.
- `Alarm Management Module` — отдельный прикладной модуль поверх `Industrial Data Platform`: alarm rules, lifecycle, acknowledgements, mutes/operator workflow и notification routing.
- `Monitoring & Alarm Platform` — deprecated composite boundary. Исторически этим термином называли вместе `Industrial Data Platform`, `Web Monitoring Module` и `Alarm Management Module`; в новой документации не используется как имя центральной системы.
- `deployment parity` — архитектурный принцип проекта: `self-hosted` и `cloud` считаются двумя deployment modes одной платформы и не должны расходиться по baseline contracts, основному data path и acceptance semantics без отдельного ADR.
- `cloud-first pilot` — первый post-MVP пилот `Industrial Data Platform` в российском облаке (`VK Cloud` или `Yandex Cloud`); self-hosted/on-prem остается future deployment mode после cloud validation.
- `local Docker infra` — локальный `Docker Compose` контур разработки, integration/smoke тестов, onboarding и воспроизведения инцидентов; не production target первого пилота.
- `internal issue tracker` — внутренний execution backlog проекта для задач, приоритетов, статусов и follow-up; не должен быть доступен первым заказчикам/партнерам с видимостью internal roadmap, commercial terms, IP/security decisions или raw backlog.

## Домен и доставка

- `alarm` — доменная сущность тревоги в платформе: правило сработало, есть жизненный цикл, severity, acknowledgement и clear.
- `notification` — внешнее сообщение по `alarm` или служебному событию, отправляемое через email, SMS, push или webhook.
- `telemetry event` — нормализованное событие наблюдения по одной точке мониторинга.
- `Local State Store` — локальное техническое SQLite-хранилище `edge_telemetry_agent` для Point State Cache, Delivery Outbox, attempts/status и warm restart.
- `Point State Cache` — persistent cache последнего наблюденного и опубликованного состояния точки, sequence и качества, используемый для фильтрации изменений и warm restart.
- `Delivery Outbox` — локальная очередь telemetry events, ожидающих надежной доставки или retry во внешний transport.
- `status topic` — transport-specific `MQTT` сообщение о состоянии southbound source или самого publisher, например `status/connection` и `status/lwt`.
- `Kafka Event Log` — логический Kafka-compatible event stream внутри `Industrial Data Platform`: topics для telemetry events, source config snapshots, source connection events, agent status events, ingestion errors и derived events. Не означает конкретный broker product.
- `Kafka-compatible broker runtime` — конкретная реализация broker-а, которая обслуживает `Kafka Event Log` через Kafka API. Локальный MVP использует `Apache Kafka`; `Redpanda broker` остается production/self-hosted candidate после отдельного compatibility PoC.
- `Redpanda Connect` — connector pipeline, который читает MQTT topics через `mqtt` input, выполняет mapping/transform и пишет records в Kafka-compatible broker через `redpanda` input/output components.
- `Redpanda broker` — Kafka-compatible broker product, который может стать runtime implementation для `Kafka Event Log` после отдельного ADR/PoC; в текущем локальном MVP broker runtime — `Apache Kafka`.
- `Telemetry Store` — authoritative analytical store на базе `ClickHouse` для append-only telemetry events, source config snapshots, source connection history, agent status history, derived events, aggregates, rollups и immutable alarm history. `alarm_history_events_v1` является storage sink, writer/owner которого находится в `Alarm Management Module`.
- `Platform Store` — transactional store на базе `PostgreSQL` для конфигурации объектов, агентов, источников и точек, shared platform state, module workflow state, audit и persistence Keycloak.
- `ClickHouse` — выбранная аналитическая БД платформы для high-volume time-series/event history и Grafana/API historical queries.
- `PostgreSQL` — выбранная транзакционная БД платформы для mutable platform state, API-конфигурации и Keycloak persistence.
- `Telemetry Consumers` — backend workers, которые читают Kafka topics и записывают canonical telemetry events, source config snapshots, source connection history, agent status history и derived events в `Telemetry Store`.
- `Streaming Analytics` — потоковая обработка telemetry stream для агрегатов, rollups, производных признаков и derived events для прикладных модулей; результаты пишет в `Telemetry Store`.
- `Grafana` — текущий read-only visualization surface внутри `Web Monitoring Module`; в production-контуре читает подготовленные данные из `Telemetry Store`.
- `Platform API` — deprecated/ambiguous umbrella term для будущих tenant-facing API. Новые API должны проектироваться как data-platform API, web-monitoring API или alarm-management API в зависимости от ownership.
- `Config Registry` — первый реализованный backend-срез `apps/idp_config_registry` / package `idp_config_registry`: хранит tenants, assets, agents, sources, points и config revisions в PostgreSQL.
- `Backoffice Admin UI` — внутренний operational UI на базе `SQLAdmin` для команды платформы; не доступен tenant/client users, допускает internal CRUD shortcut, а выпуск config state выполняется отдельным render action через application use cases и transactional outbox.
- `Web Monitoring Frontend` — future browser-приложение модуля мониторинга, которое будет аутентифицироваться через Keycloak и работать с data-platform/read API; в текущем MVP отдельный frontend еще не реализован.
- `Keycloak` — IAM-компонент платформы: пользователи, группы, роли, OIDC clients, sessions и JWT issuance.
- `JWT` — access token, выпускаемый Keycloak и валидируемый будущими tenant-facing API локально по OIDC discovery/JWKS.
- `API Gateway` — application-level gateway перед несколькими backend API; решение по нему выносится в отдельный ADR.
- `southbound-адаптеры` — адаптеры и драйверы, через которые `edge_telemetry_agent` подключается вниз по стеку к полевым протоколам и локальным источникам данных, например `KNX`, `OPC UA`, `Modbus`, `SCADA`.
- `OPC UA read-only ingestion` — следующий выбранный post-MVP protocol track: `edge_telemetry_agent` работает как `OPC UA client`, только считывает данные из `OPC UA server` и мапит nodes в существующую `source/point` model без управляющих команд из Web Monitoring UI/API.
- `write/control path` — в Web Monitoring документации означает только управляющие команды в промышленный контур из web UI/API; не относится к техническим platform writes вроде telemetry/status storage, config revisions, outbox, audit или alarm workflow state.
- `northbound delivery` — доставка данных вверх по стеку из `edge_telemetry_agent` в `Industrial Data Platform` через внешний transport, например `MQTT`.

## Конфигурационная модель

- `bootstrap config` — минимальная локальная конфигурация запуска edge-telemetry-agent: `agent_id`, MQTT endpoint, credentials/secret refs, local storage и observability. Не содержит registry sources/points.
- `server-issued config` — конфигурация runtime, выданная платформенным контуром через retained MQTT topics.
- `agent runtime config` — retained root config агента `idp.edge.agent-runtime-config.v1`: `tenant_id`, `asset_id`, `agent_id`, `config_revision` и список активных sources.
- `source config` — retained config конкретного `source_id` `idp.edge.source-config.v1`: connection settings, points, acquisition/publish policies и metadata точек.
- `config revision` — стабильная версия root agent runtime config, выпускаемая через Kafka-first delivery log и применяемая edge-telemetry-agent после материализации в MQTT retained topics.
- `source_config_revision` — стабильная версия source config, которую telemetry event указывает как metadata context.
- `config event publisher` — backend worker, который читает единственную PostgreSQL таблицу `config_outbox` и публикует `idp.edge.config.delivery.v1` records в Kafka topic `idp.edge.configs.v1`.
- `source config snapshot projector` — consumer, который читает `idp.edge.configs.v1` и публикует canonical `idp.source.config.v1` records в `idp.source.configs.v1`.
- `edge config MQTT projector` — Redpanda Connect pipeline, который читает `idp.edge.configs.v1` и материализует retained MQTT topics для edge-telemetry-agent.
- `config delivery projection` — materialized MQTT retained topics, которые Redpanda Connect строит из Kafka config delivery records для edge-telemetry-agent.
- `transactional outbox` — паттерн надежной интеграции PostgreSQL и Kafka: domain change и outbox record записываются атомарно в PostgreSQL, а отдельный publisher доставляет запись во внешний broker с retry и idempotency.
- `YAML config bundle` — versioned import/bootstrap artifact для seed и support-сценариев; после появления `Config Registry` не конкурирует с `Config Registry`/`Platform Store` как source of truth и служит входом для publish/import workflow.
- `source` — логическое подключение агента к конкретному источнику данных, идентифицируемое `source_id`.
- `point` — точка мониторинга внутри `source`, идентифицируемая `point_ref`.
- `point_ref` — технический идентификатор точки внутри источника, например group address, node id или register reference.
- `point_key` — safe representation от `point_ref`, используемое в `MQTT` topic path.
- `contract-id` — стабильное имя версии контракта данных, например `edge.telemetry-event.v1` или `idp.edge.telemetry.event.v1`.

## Контракты данных

- `Contract Registry` — каталог `docs/contracts/`, единственный source of truth для схем сообщений, локальных структур данных, topic/table names и boundary contracts.
- `apps/*/docs` — guide-документация по использованию контрактов; она не должна становиться вторым source of truth для полного списка полей.
