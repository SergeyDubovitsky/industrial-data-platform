# Текущее состояние системы

Дата: 2026-05-10
Статус: working snapshot

Этот документ является коротким operational snapshot для людей и AI-agent.
Он описывает текущее состояние системы без истории решений. Активные решения
сведены в `docs/architecture/decisions.md`; принятые исторические ADR остаются
архивным rationale в `docs/architecture/adrs/archive/`, а proposed ADR могут
жить рядом с `docs/architecture/adrs/README.md` до решения команды.

## Статус MVP

Проект уже достиг `MVP baseline`.

Под `MVP` в текущем репозитории понимается не “полная платформа во всех
компонентах”, а уже реализованный рабочий baseline:

- `Edge Telemetry Agent`
- server-issued agent runtime config через retained `MQTT`
- reliable telemetry delivery через `MQTT`
- локальный ingestion slice `MQTT -> Redpanda Connect -> Apache Kafka`
- versioned config bundle и integration-тесты для этого контура

Поверх этого baseline в текущей ветке уже реализованы первые data-platform
foundation инкременты: `Config Registry` на `PostgreSQL`, Kafka-first config
delivery, локальный `ClickHouse Telemetry Store` path и `Grafana` read-model
surface как первый `Web Monitoring Module` surface.

## Назначение

Система строится прежде всего как `Industrial Data Platform`: промышленное ядро
сбора, доставки, конфигурации и хранения данных. `Web Monitoring` и
`Alarm Management` являются отдельными модулями поверх этого ядра.

Целевая линия:

- `Edge Telemetry Agent` работает рядом с объектом автоматизации.
- Agent читает данные из southbound-источников, нормализует наблюдения,
  фильтрует изменения, хранит техническое состояние в SQLite и доставляет
  события наружу.
- `Industrial Data Platform` принимает поток, валидирует и обогащает его,
  пишет события в Kafka-compatible event log и хранилища, а прикладные модули
  читают подготовленные данные и используют shared platform services.
- `Industrial Data Platform` должна поддерживать два deployment modes:
  `self-hosted` и `cloud`, без расхождения по основным contracts и data path.
- Первый post-MVP пилот запускается cloud-first в российском облаке (`VK Cloud`
  или `Yandex Cloud`), потому что on-prem/self-hosted инфраструктура первых
  заказчиков пока не готова.

## Что реализовано сейчас

- Monorepo с Python workspace, LikeC4-моделью, архитектурными документами и
  contract registry.
- `Edge Telemetry Agent` с bootstrap config, загрузкой retained agent runtime/source
  config из MQTT, fail-fast validation и CLI:
  `check-config`, `show-config`, `enqueue-demo-event`, `deliver-once`.
- Runtime-модель `tenant_id`, `asset_id`, `agent_id`, `source_id`,
  `point_ref`, `point_key`, `config_revision` и `source_config_revision`.
- Processing pipeline для observation -> normalized telemetry event:
  подавление непубликуемых `command`-точек, threshold/change filtering,
  sequence/value metadata и quality.
- `SQLite` technical state: point state cache и delivery outbox для retry.
- MQTT delivery slice для telemetry events, source connection status и agent LWT.
- Demo/config bundle для `demo-stand` и первый `KNX`-срез.
- `Config Registry` foundation: FastAPI backend на clean architecture,
  PostgreSQL persistence, Alembic migrations, transactional outbox и Kafka
  config delivery publisher.
- Local development stack: MQTT broker, Apache Kafka, Redpanda Connect
  ingestion/config projection pipelines, PostgreSQL, ClickHouse, Kafka Connect
  и provisioned Grafana.
- `Kafka Event Log` зафиксирован как логический Kafka-compatible event stream:
  локальный broker runtime сейчас `Apache Kafka`, а `Redpanda broker` остается
  candidate после отдельного compatibility PoC.
- `docs/contracts/` как канонический каталог схем, topic names, Kafka topics,
  ClickHouse contract tables и boundary rules.

## Что остается post-MVP развитием

- Расширение `Industrial Data Platform` от текущего `MVP baseline` до
  production-инсталляции: production `MQTT Ingestion Gateway`, production
  Kafka-compatible broker runtime, storage writer/Kafka Connect,
  `Streaming Analytics`, `Telemetry Store`, `Platform Store`, `Config Registry`
  и shared IAM. Локально уже есть foundation-срезы `Config Registry`,
  `ClickHouse`, `Kafka Connect` и `Grafana`, но core runtime еще не доведен до
  production-grade.
- Развитие `Web Monitoring Module`: Grafana/read dashboards уже представлены
  локально, полноценный monitoring frontend и tenant-facing read API остаются
  следующим модульным слоем поверх data platform.
- Развитие `Alarm Management Module`: `Alarm Rule Engine`, alarm lifecycle,
  current alarm workflow state и `Notification Service` являются отдельным
  модулем поверх data platform, а не частью ingestion/storage core.
- Production hardening существующих foundation stores: `ClickHouse` как
  `Telemetry Store` и `PostgreSQL` как `Platform Store` уже представлены в
  локальном dev/integration контуре, но не доведены до production sizing,
  backup/restore, HA и операционных процедур.
- Расширение `Config Registry` от текущего foundation-среза до tenant-facing
  data-platform backend: authn/authz, richer revision workflow, rollout controls,
  approval/publish process и API boundaries beyond current internal/backoffice
  scope.
- `Hierarchical Catalog V1` вынесен в working-plan как candidate
  navigation/authoring tree поверх registry entities: один default tree на
  tenant, произвольно вложенные catalog nodes и references на
  assets/agents/sources/points через public codes. Он намеренно отделен от
  будущего `Digital Twin Registry` / `Asset Graph Registry`, где появятся
  arbitrary attributes, non-tree relations и telemetry bindings. Runtime
  placement остается открытым и сравнивается в draft ADR-015.
- Tenant-facing UI для редактирования agent runtime/source config. На текущем этапе
  source of truth уже переехал в `Config Registry`/`PostgreSQL`, а versioned
  YAML bundle остается import/bootstrap path; полноценный внешний UI и workflow
  публикации остаются следующими шагами.
- Расширение southbound-адаптеров. Текущий практический срез остается
  `KNX-first`, а следующий выбранный protocol track — `OPC UA read-only
  ingestion`: `edge_telemetry_agent` работает как `OPC UA client` и только считывает
  данные из `OPC UA server`. `Modbus TCP`, `DB` и другие источники остаются
  future adapters.
- Production security hardening: TLS/certificates/ACL/secrets lifecycle,
  конкретные broker policies, production observability и support workflows.

## Production Boundaries

В production data path система является read-only контуром сбора и хранения
данных:

- edge-telemetry-agent читает и наблюдает сигналы;
- управляющие команды из Web Monitoring UI/API не входят в первый продуктовый
  scope;
- технические platform writes для telemetry/status storage, config revisions,
  outbox, audit и alarm workflow state остаются частью платформы;
- полноценная `SCADA/HMI` не входит в текущий объем;
- автоматическое полное discovery всех тегов и информационных моделей не
  входит в текущий объем;
- edge SQLite не является историческим архивом телеметрии;
- локальный `MQTT/Kafka` stack является dev/integration slice, а не полной
  production platform.

Для `Industrial Data Platform` действуют дополнительные границы deployment-модели:

- `self-hosted` и `cloud` считаются двумя вариантами поставки одной и той же
  `Industrial Data Platform` с модулями поверх нее, а не двумя разными
  архитектурами;
- первый pilot target для `Industrial Data Platform` — cloud-first в российском
  облаке; self-hosted/on-prem остается целевым mode после cloud validation и
  готовности инфраструктуры заказчика;
- baseline contracts, основной ingestion/data path и acceptance criteria должны
  совпадать между deployment modes;
- cloud-managed optimization допустима только если она не создает отдельный
  cloud-only contract path и не ломает parity с `self-hosted`.
- локальная `Docker Compose` infra является обязательным dev/test baseline для
  integration-тестов, smoke-тестов, onboarding и воспроизведения инцидентов, но
  не считается production target первого пилота.

Отдельный пилот `KNX -> OPC` может иметь write-path из внешнего OPC-клиента,
но это отдельный сервисный контур, не основной data-platform data path.

## Source Of Truth

| Область | Source of truth |
| --- | --- |
| Текущий снимок системы | `docs/architecture/current-state.md` |
| Активные архитектурные решения | `docs/architecture/decisions.md` |
| Proposed/исторические ADR и trade-off | `docs/architecture/adrs/`, `docs/architecture/adrs/archive/` |
| Карта систем и контейнеров | `arch/likec4/` |
| Термины | `docs/architecture/glossary.md` |
| Открытые вопросы | `docs/architecture/open-questions.md` |
| Контракты данных, MQTT/Kafka topics и table names | `docs/contracts/` |
| Edge guide-документация | `apps/edge_telemetry_agent/docs/` |
| Demo/agent runtime config bundle | `environments/demo-stand/edge_telemetry_agent/` |
| Execution backlog, приоритеты и статусы | internal issue tracker |

## Agent Reading Guide

Для большинства задач агенту не нужно читать архивные ADR. Используйте такой
порядок:

1. Для ориентации: этот документ и `docs/architecture/glossary.md`.
2. Для активных архитектурных решений: `docs/architecture/decisions.md`.
3. Для edge agent runtime config: `docs/contracts/edge-telemetry-agent/`.
4. Для MQTT delivery и topic tree:
   `docs/contracts/edge-telemetry-agent/mqtt-topic-tree.v1.md`.
5. Для identity model: `docs/contracts/edge-telemetry-agent/` и
   `docs/contracts/platform-ingestion/`.
6. Для границ data platform, web monitoring и alarms: этот документ,
   `docs/architecture/decisions.md` и LikeC4.
7. Для storage/platform design: `docs/contracts/clickhouse/` и
   `docs/contracts/kafka/`.
8. Для backend хранения настроек платформы: `apps/idp_config_registry/README.md`,
   `docs/contracts/edge-telemetry-agent/config-revision-model.md` и
   `docs/architecture/hierarchical-catalog-v1.md`.
9. Для deployment parity, cloud-first pilot, `OPC UA` read-only track и internal
   execution backlog: этот документ, `solution-architecture.md` и
   `open-questions.md`.
10. Для KNX-first MVP behavior: `solution-architecture.md` и
    `apps/edge_telemetry_agent/docs/data-contracts.md`.

Если архивный ADR и `docs/contracts/` расходятся по полям сообщения,
topic/table names или schema details, приоритет у `docs/contracts/`. Архивный
ADR объясняет решение, но не заменяет contract registry.

## Next Decisions

Ближайшие развилки ведутся в `docs/architecture/open-questions.md`. Критичные
темы сейчас:

- production MQTT broker, TLS, ACL и secrets handling;
- limits и lifecycle для retained agent runtime/source config;
- эволюция YAML config bundle из import/bootstrap path в полностью data-platform-led
  authoring workflow;
- concrete `VK Cloud` vs `Yandex Cloud` choice, managed-service packaging and
  secrets backend for the cloud-first pilot;
- production host/deployment model для edge runtime;
- candidate `Hierarchical Catalog V1` vs future `Digital Twin Registry` /
  `Asset Graph Registry`: сначала нужно выбрать scope (navigation tree или
  twin/asset graph), затем runtime boundary. Working plan описан в
  `docs/architecture/hierarchical-catalog-v1.md`, comparison вынесен в draft
  ADR-015, решение еще не принято как `decisions.md` entry;
- кандидат для следующего Industrial Data Platform / Web Monitoring обсуждения: нужен ли
  read-only `latest/history` API поверх существующих ClickHouse views
  `telemetry_latest_v1` и `telemetry_events_dedup_v1`; это отдельная
  tenant-facing read API boundary, не расширение `Config Registry`, и она не
  включает UI, alarm workflow, RBAC или write-back/control. Материал к обсуждению:
  `docs/architecture/read-only-telemetry-api-discussion.md`.
