# Industrial Data Platform

[![Coverage](https://raw.githubusercontent.com/SergeyDubovitsky/industrial-data-platform/badges/coverage.svg)](https://github.com/SergeyDubovitsky/industrial-data-platform/actions/workflows/python-ci.yml)

Репозиторий организован как monorepo для `Edge Telemetry Agent`,
`Industrial Data Platform`, прикладных модулей `Web Monitoring` /
`Alarm Management`, Python-утилит и архитектурных артефактов.

`Industrial Data Platform` — новое имя центрального ядра сбора, доставки,
конфигурации и хранения данных. Старое имя `Monitoring & Alarm Platform`
считается deprecated composite boundary для исторических документов, где вместе
назывались data platform, web monitoring и alarm workflow.

## Статус проекта

Проект уже достиг `MVP baseline`.

Текущий `MVP baseline` в репозитории:

- `Edge Telemetry Agent` с bootstrap-конфигом, загрузкой retained agent runtime/source config из `MQTT`, processing pipeline и `SQLite Delivery Outbox`
- локальный platform slice `MQTT -> Redpanda Connect -> Apache Kafka`
- versioned config bundle для `demo-stand`
- contract registry, архитектурные документы и integration-тесты для этого потока

Поверх `MVP baseline` в текущей ветке уже реализованы первые data-platform
foundation slices:

- `Config Registry` на `FastAPI + PostgreSQL` с `tenant/asset/agent/source/point` CRUD, render config revisions и transactional outbox
- Kafka-first config delivery path `PostgreSQL -> idp.edge.configs.v1 -> Redpanda Connect -> retained MQTT agent runtime/source config`
- локальный storage/read path `Kafka -> Kafka Connect -> ClickHouse`, `Grafana`
  datasource provisioning и read-model PoC как первый surface `Web Monitoring Module`
- `Kafka Event Log` рассматривается как логический Kafka-compatible слой:
  локальный broker runtime сейчас `Apache Kafka`, а `Redpanda broker` оставлен
  для отдельного compatibility PoC.

Первый post-MVP пилот идет cloud-first в российском облаке; приоритетные
кандидаты — `VK Cloud` или `Yandex Cloud`.

Локальная Docker-инфра остается обязательной для разработки, integration-тестов,
smoke-тестов, onboarding и воспроизведения инцидентов. Она не является
production target первого пилота, но должна оставаться близкой к cloud/self-hosted
baseline по contracts, migrations и operational semantics.

Целевая `Industrial Data Platform` продолжает проектироваться для двух
deployment modes: `self-hosted` и `cloud`.

Для них сохраняется общий baseline:

- одинаковые контракты данных и topic/table names
- один и тот же основной data path
- минимальные отличия в migration artifacts, observability и операционной модели

Расширение идет по трем границам: production-grade `Industrial Data Platform`
с `Telemetry Store`, `Platform Store` и production IAM; отдельный
`Web Monitoring Module` для dashboards/history/operator read UI; отдельный
`Alarm Management Module` для правил, lifecycle, workflow и notifications.

## Структура

- [`apps/edge_telemetry_agent/`](apps/edge_telemetry_agent/) — edge runtime, example-конфиги и runtime-guides
- [`apps/knx_demo/`](apps/knx_demo/) — KNX demo utilities
- [`apps/idp_config_registry/`](apps/idp_config_registry/) — первый backend-срез `Industrial Data Platform Config Registry`
- [`libs/knx_project_parser/`](libs/knx_project_parser/) — библиотека для разбора ETS `.knxproj`
- [`libs/idp_demo_stack/`](libs/idp_demo_stack/) — библиотека demo/scenario потока `config bundle -> Config Registry API -> outbox worker -> Kafka config delivery -> retained MQTT config -> telemetry`
- [`tools/idp_telemetry_store/`](tools/idp_telemetry_store/) — repo-native operational tooling и migration CLI для `Industrial Data Platform Telemetry Store`
- [`environments/`](environments/) — versioned edge profiles конкретных стендов и окружений
- [`infra/`](infra/) — локальная Docker-инфраструктура разработки и integration-тестов
- [`docs/contracts/`](docs/contracts/) — канонические MQTT/Kafka/ClickHouse/storage контракты
- [`docs/architecture/`](docs/architecture/) — архитектурные документы и ADR верхнего уровня
- [`docs/agents/`](docs/agents/) — agent workflows, roles, templates и module map
- [`docs-site/`](docs-site/) — внутренний Starlight docs-site поверх curated markdown-документации
- [`docs/future-ideas.md`](docs/future-ideas.md) — идеи и возможные следующие инкременты, не текущий backlog
- [`arch/`](arch/) — LikeC4-модель и связанные материалы
- [`tests/integration/`](tests/integration/) — end-to-end проверки локального platform slice

Правило именования верхнего уровня:

- `apps/` — deployable или operator-facing сервисы и приложения
- `libs/` — импортируемые Python-пакеты, которые используются как библиотеки из кода или тестов
- `tools/` — repo-native tooling, migration CLI, one-off operational helpers и automation packages

По этой причине `knx_project_parser` и `idp_demo_stack` остаются в `libs/`: оба уже живут как
workspace packages с `src/`, тестами и импортируемым API, а `idp_demo_stack`
используется в integration-тестах как библиотека, а не только как CLI.

## Code Ownership Map

Текущая ownership-карта разнесена без физического переименования packages:

- `Industrial Data Platform`: `apps/idp_config_registry`, `tools/idp_telemetry_store`, `infra/local` сервисы `mqtt-broker`, `kafka`, `redpanda-connect`, `kafka-connect`, `clickhouse`, `postgres`, `idp-config-registry` и `idp-config-registry-outbox-worker`.
- `Web Monitoring Module`: `infra/local/grafana` и integration surface `Grafana -> ClickHouse read models`.
- `Edge Telemetry Agent`: `apps/edge_telemetry_agent`, edge profiles в `environments/` и KNX/parser tooling.
- `Demo/integration glue`: `libs/idp_demo_stack`; это не production module boundary.
- `Alarm Management Module`: runtime package пока отсутствует и будет добавлен отдельным инкрементом после выбора alarm use cases.

## Working With Agents

Для AI-агентов tracked entrypoint находится в [`AGENTS.md`](AGENTS.md).
Порядок чтения:

1. root [`AGENTS.md`](AGENTS.md)
2. ближайший scoped `AGENTS.md` в затронутой директории
3. [`docs/agents/module-map.yaml`](docs/agents/module-map.yaml)
4. нужные contracts, ADR и LikeC4 source files

`CLAUDE.md` и `.github/copilot-instructions.md` являются compatibility bridges
и не должны дублировать полную политику репозитория. Локальные scratch runs
остаются в `.local/` и не трекаются git.

## Task Tracking

Internal issue tracker — source of truth для текущих задач, приоритетов и
статуса выполнения.

- internal issue tracker хранит execution backlog, приоритеты, статусы,
  follow-up задачи и future analysis
- external customers/partners не должны иметь доступ к internal roadmap,
  commercial terms, product/IP strategy, security decisions и raw backlog
- customer feedback переносится в internal issue tracker вручную или через
  отдельный customer-facing project/helpdesk/view без internal fields
- git-документация хранит архитектуру, ADR, product boundaries, открытые вопросы
  и future ideas
- живые execution plans не поддерживаются в репозитории, чтобы не расходиться с
  internal issue tracker

## Python Workspace

Базовый workflow выполняется из корня репозитория:

```bash
test -f .env || cp .env.example .env
uv sync
uv run --package edge-telemetry-agent pytest apps/edge_telemetry_agent/tests
uv run --package knx-demo pytest apps/knx_demo/tests
uv run --package idp-config-registry pytest apps/idp_config_registry/tests
uv run --package knx-project-parser pytest libs/knx_project_parser/tests
uv run --group integration pytest libs/idp_demo_stack/tests/test_scenario.py
```

Для линтинга Python-кода:

```bash
uv sync --group lint
uv run --group lint ruff check apps libs tests infra tools
```

Для интеграционных тестов локального MQTT/Kafka-контура:

```bash
uv sync --all-packages --group integration
docker compose --env-file .env.example -f infra/local/compose.yaml build \
  kafka-connect grafana idp-config-registry
uv run --group integration pytest \
  tests/integration/test_config_registry_kafka_publisher.py \
  tests/integration/test_config_registry_postgres.py \
  tests/integration/test_edge_agent_mqtt_publisher.py \
  tests/integration/test_edge_agent_knx_to_mqtt.py \
  tests/integration/test_kafka_to_clickhouse_storage.py \
  tests/integration/test_grafana_clickhouse.py
```

Быстрый smoke-срез:

```bash
uv run --group integration pytest tests/integration -m integration_smoke
```

Integration fixtures переиспользуют основные Docker Compose stack в пределах
pytest session; Postgres-only fixture остается module-scoped, чтобы API
persistence assertions не видели данные из других модулей. Изоляция сценариев
держится через уникальные tenant/key/event ids,
targeted cleanup таблиц и фильтрацию Kafka records по ожидаемым ключам.
Предварительный `docker compose build` не обязателен, если локальные images уже
собраны, но в CI его стоит выполнять один раз перед `pytest`, а не внутри
каждого тестового setup.

Текущее покрытие integration-набора:

- `tests/integration/test_config_registry_kafka_publisher.py` —
  `Config Registry -> Kafka config delivery -> Redpanda Connect -> retained MQTT`
  и end-to-end seed через `idp-demo-stack publish-edge-demo`
- `tests/integration/test_config_registry_postgres.py` — `Config Registry -> PostgreSQL`
  через Alembic migration и FastAPI tenant endpoints
- `tests/integration/test_edge_agent_mqtt_publisher.py` — raw `paho` publisher smoke и CLI-path `enqueue-demo-event -> deliver-once -> MQTT`
- `tests/integration/test_edge_agent_knx_to_mqtt.py` — lower-level edge-telemetry-agent smoke: `Kafka config delivery fixture -> retained MQTT config -> ObservationProcessor -> SQLite outbox -> DeliveryWorker -> MQTT -> Redpanda Connect -> Apache Kafka`
- `tests/integration/test_kafka_to_clickhouse_storage.py` —
  `Kafka -> Kafka Connect -> ClickHouse raw landing -> contract table`,
  включая byte-for-byte проверку `payload_json` и storage DLQ для невалидных
  records
- `tests/integration/test_grafana_clickhouse.py` — provisioning и чтение
  `Grafana -> ClickHouse` read models поверх локального `Telemetry Store`

Для host-side запуска приложений используйте общий root `.env` через
`uv run --env-file .env ...`.

Полезные package-scoped команды:

- `uv run --package edge-telemetry-agent edge-telemetry-agent --help`
- `uv run --package edge-telemetry-agent edge-telemetry-agent check-config`
- `uv run --package knx-demo knx-demo --help`
- `uv run --package idp-config-registry idp-config-registry`
- `uv run --env-file .env --package idp-config-registry alembic -c apps/idp_config_registry/alembic.ini upgrade head`
- `uv run --package knx-project-parser knx-project-parser --help`
- `uv run --env-file .env --package idp-demo-stack publish-edge-demo --help`
- `uv run idp-telemetry-store migrate status`

## Архитектурные Артефакты

- [`docs/architecture/current-state.md`](docs/architecture/current-state.md) — короткий снимок текущего состояния
  системы для ориентации людей и AI-agent без чтения всех ADR
- [`docs/architecture/README.md`](docs/architecture/README.md) — навигация по архитектурным документам
- [`docs/architecture/solution-architecture.md`](docs/architecture/solution-architecture.md) — целевая архитектура
  edge-сервиса, dataflow и deployment
- [`docs/architecture/glossary.md`](docs/architecture/glossary.md) — канонический словарь архитектурных терминов
- [`docs/architecture/open-questions.md`](docs/architecture/open-questions.md) — список открытых вопросов к заказчику
  и по эксплуатации
- [`docs/architecture/decisions.md`](docs/architecture/decisions.md) — компактный register активных архитектурных решений
- [`docs/architecture/adrs/`](docs/architecture/adrs/) — архив historical rationale; навигация начинается
  с [`docs/architecture/adrs/README.md`](docs/architecture/adrs/README.md)
- [`docs-site/`](docs-site/) — внутренний Starlight docs-site поверх curated markdown-документации
- [`docs/contracts/README.md`](docs/contracts/README.md) — реестр контрактов данных и единый source of truth
- [`docs/contracts/edge-telemetry-agent/`](docs/contracts/edge-telemetry-agent/) — канонические edge boundary contracts, MQTT topic tree и схемы payload
- [`arch/likec4/`](arch/likec4/) — source of truth для C4-модели и диаграмм
- [`arch/README.md`](arch/README.md) — навигация по LikeC4-модели и командам
- [`apps/edge_telemetry_agent/docs/data-contracts.md`](apps/edge_telemetry_agent/docs/data-contracts.md) — guide по edge runtime dataflow,
  конфигурационной модели и ссылкам на канонические схемы
- [`apps/edge_telemetry_agent/docs/mqtt-topics.md`](apps/edge_telemetry_agent/docs/mqtt-topics.md) — guide по MQTT publish contract и
  ссылкам на канонический topic tree
- [`apps/edge_telemetry_agent/config/examples/bootstrap.example.yaml`](apps/edge_telemetry_agent/config/examples/bootstrap.example.yaml) — bootstrap example для edge agent
- [`apps/edge_telemetry_agent/config/examples/config.bundle.example.yaml`](apps/edge_telemetry_agent/config/examples/config.bundle.example.yaml) — config bundle example для Kafka-first retained agent runtime/source config projection
- [`apps/edge_telemetry_agent/config/README.md`](apps/edge_telemetry_agent/config/README.md) — описание структуры конфигурации и разделения examples/environment configs

## LikeC4

Команды для архитектурной модели выполняются из `arch/`:

```bash
cd arch
npm run validate
npm run build
```

## Local Infrastructure

Локальный dev-стек описан в [`infra/local/`](infra/local/).
Быстрый старт:

```bash
test -f .env || cp .env.example .env
./infra/local/up-platform.sh
```

Если `.env` уже существует, не перезаписывайте его: перенесите недостающие
ключи из `.env.example` вручную. `up-platform.sh` запускается из корня
репозитория, сам использует root `.env`,
пересобирает локальные image для `idp-config-registry`, `grafana` и
`kafka-connect`, выполняет Alembic migrations для `Config Registry` и только
потом поднимает полный local platform slice.

Если нужен только минимальный `MQTT`-срез:

```bash
docker compose -f infra/local/compose.yaml --env-file .env up -d mqtt-broker
```

Рекомендуемый локальный flow после старта стека:

1. Запаблишить demo config:

```bash
uv run --env-file .env --package idp-demo-stack publish-edge-demo \
  --bundle-config environments/demo-stand/edge_telemetry_agent/config.bundle.yaml
```

2. Проверить bootstrap + retained config path агента:

```bash
uv run --env-file .env --package edge-telemetry-agent edge-telemetry-agent check-config \
  --bootstrap-config environments/demo-stand/edge_telemetry_agent/bootstrap.yaml
```

3. Открыть UI и диагностические поверхности:

- `Config Registry API`: [http://localhost:8000](http://localhost:8000)
- `Config Registry Backoffice`: [http://localhost:8000/backoffice](http://localhost:8000/backoffice)
  доступен только когда `CONFIG_REGISTRY_INTERNAL_MODE=true`
- `Kafka UI`: [http://localhost:8080](http://localhost:8080)
- `MQTTX Web`: [http://localhost:8081](http://localhost:8081)
- `Grafana`: [http://localhost:3000](http://localhost:3000)

Сервисные endpoint и порты:

- `MQTT broker`: `mqtt://localhost:1883`
- `MQTT over WebSocket`: `ws://localhost:9001`
- `Kafka host listener`: `localhost:19092`
- `Redpanda Connect MQTT -> Kafka`: [http://localhost:4195](http://localhost:4195)
- `Redpanda Connect Kafka -> MQTT config projection`: [http://localhost:4196](http://localhost:4196)
- `Redpanda Connect source config snapshot projector`: [http://localhost:4197](http://localhost:4197)
- `Kafka Connect REST`: [http://localhost:8083](http://localhost:8083)
- `Kafka Connect JMX`: `localhost:9102`
- `ClickHouse HTTP`: [http://localhost:8123](http://localhost:8123)
- `ClickHouse native`: `localhost:9000`
- `PostgreSQL`: `localhost:5432`

Credentials и переменные окружения:

- `MQTT broker` использует `MQTT_USERNAME` и `MQTT_PASSWORD`
- `ClickHouse` использует `CLICKHOUSE_DATABASE`, `CLICKHOUSE_USER` и `CLICKHOUSE_PASSWORD`
- `Grafana` использует `GRAFANA_ADMIN_USER` и `GRAFANA_ADMIN_PASSWORD`
- `PostgreSQL` использует `POSTGRES_DB`, `POSTGRES_USER` и `POSTGRES_PASSWORD`

Для `edge_telemetry_agent` уже подготовлен bootstrap + config bundle профиль под этот стек:

```bash
uv run --env-file .env --package edge-telemetry-agent edge-telemetry-agent check-config \
  --bootstrap-config environments/demo-stand/edge_telemetry_agent/bootstrap.yaml
```

Для текущего удаленного dev-сценария demo-стенда есть отдельный профиль:

```bash
uv run --env-file .env --package edge-telemetry-agent edge-telemetry-agent check-config \
  --bootstrap-config environments/demo-stand-remote/edge_telemetry_agent/bootstrap.yaml
```

Если нужно seed-ить config delivery records именно для remote-profile:

```bash
uv run --env-file .env --package idp-demo-stack publish-edge-demo \
  --bundle-config environments/demo-stand-remote/edge_telemetry_agent/config.bundle.yaml
```

Для автоматизированной проверки используйте integration-набор:

```bash
uv run --group integration pytest \
  tests/integration/test_config_registry_kafka_publisher.py \
  tests/integration/test_config_registry_postgres.py \
  tests/integration/test_edge_agent_mqtt_publisher.py \
  tests/integration/test_edge_agent_knx_to_mqtt.py \
  tests/integration/test_kafka_to_clickhouse_storage.py \
  tests/integration/test_grafana_clickhouse.py
```

Отдельные операционные команды:

ClickHouse migrations выполняются из корня репозитория:

```bash
uv run --env-file .env idp-telemetry-store migrate status
uv run --env-file .env idp-telemetry-store migrate up
```

Kafka Connect connector для raw landing path применяется так:

```bash
uv run --env-file .env python infra/local/kafka-connect/bootstrap_connector.py
```

ClickHouse analytical read-model PoC:

```bash
uv run --env-file .env idp-telemetry-store load-poc telemetry-read-models \
  --rows 50000 \
  --points 100 \
  --batch-size 10000 \
  --duplicate-every 10
```

После загрузки PoC откройте `Grafana -> Web Monitoring -> Telemetry Overview`.
Dashboard читает `telemetry_latest_v1`, `telemetry_1m_v1`,
`telemetry_1h_v1` и ingestion diagnostics из ClickHouse. Это локальная
read-only поверхность поверх ClickHouse read models; старый MQTT/Grafana
dashboard path не используется.
