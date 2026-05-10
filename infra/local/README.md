# Локальный Industrial Data Platform stack

Этот каталог хранит локальный docker compose стек для разработки и
интеграционных тестов вокруг `edge_telemetry_agent`, `Industrial Data Platform`
foundation и первого `Web Monitoring Module` surface.

Основной сценарий сейчас такой:

- поднять локальный `MQTT broker`
- поднять локальный `Apache Kafka` как Kafka-compatible event log
- поднять `Redpanda Connect` как ingestion pipeline `MQTT -> Kafka`
- поднять `Redpanda Connect` как config projection pipeline
  `Kafka -> MQTT retained`
- поднять `Redpanda Connect` как source config snapshot pipeline
  `Kafka edge configs -> Kafka source configs`
- поднять `ClickHouse` как локальный `Telemetry Store` foundation
- поднять `PostgreSQL` как локальный `Platform Store` foundation для
  `Config Registry`
- поднять `Config Registry API` как отдельный backend-контейнер
- поднять `Config Registry Outbox Worker` как отдельный worker-контейнер
- поднять `Kafka Connect` с `ClickHouse Kafka Connect Sink`
- поднять `Grafana` как локальный `Web Monitoring Module` surface с
  provisioned ClickHouse datasource/dashboard
- запаблишить config delivery records из `config.bundle.yaml` в Kafka
- проверить поток
  `KNX-shaped telemetry -> edge_telemetry_agent -> MQTT -> Kafka -> ClickHouse landing`

Этот stack не использует Redpanda broker: `Kafka Event Log` обслуживает
локальный `Apache Kafka`, а `Redpanda Connect` используется только как
connector runtime для MQTT/Kafka projection. Активное решение по broker runtime
сведено в `docs/architecture/decisions.md`.

## Что поднимается

Ownership в этом stack:

- `Industrial Data Platform`: MQTT/Kafka ingestion, Redpanda Connect
  pipelines, Kafka Connect, ClickHouse, PostgreSQL, Config Registry API и
  Config Registry Outbox Worker.
- `Web Monitoring Module`: Grafana datasource/dashboard поверх ClickHouse read
  models.
- `Demo/integration glue`: seed/publish helpers из `idp-demo-stack`.
- `Alarm Management Module`: runtime service пока не представлен в local stack.

- `mqtt-broker` — локальный `Eclipse Mosquitto`
- `kafka` — локальный single-node `Apache Kafka` в KRaft mode
- `kafka-init` — одноразовое создание platform topics, storage DLQ topic и
  internal topics будущего Kafka Connect runtime
- `redpanda-connect` — connector pipeline, который читает `idp/v1/#`,
  поддерживает enrichment cache из `idp.source.configs.v1` и retained source
  config projection, но не строит `idp.source.configs.v1` из MQTT, и пишет
  telemetry/status records в Kafka
- `redpanda-connect-config-projection` — connector pipeline, который читает
  `idp.edge.configs.v1` и материализует retained agent runtime/source
  config topics для edge-telemetry-agent
- `redpanda-connect-source-config-snapshot` — connector pipeline, который
  строит canonical `idp.source.config.v1` snapshots из
  `idp.edge.configs.v1`
- `clickhouse` — локальный `ClickHouse` для пути
  `Kafka -> Kafka Connect -> ClickHouse` и read models для Grafana
- `postgres` — локальный `PostgreSQL` для `Config Registry`
- `idp-config-registry` — FastAPI backend контейнер для registry write/read API
- `idp-config-registry-outbox-worker` — отдельный worker-контейнер, который
  непрерывно публикует `config_outbox` records в
  `idp.edge.configs.v1`
- `kafka-connect` — distributed Kafka Connect worker с установленным
  `ClickHouse Kafka Connect Sink`
- `kafka-ui` — web UI для просмотра Kafka topics/messages
- `mqttx-web` — web MQTT-клиент для ручной подписки на MQTT topics
- `grafana` — локальный `Web Monitoring Module` dashboard над ClickHouse read models

## Быстрый старт

Команды ниже предполагают запуск из корня репозитория и наличие `.env`
рядом с `.env.example`.

Только MQTT-срез:

```bash
docker compose -f infra/local/compose.yaml --env-file .env up -d mqtt-broker
```

Полный local `Industrial Data Platform` slice с Web Monitoring surface:

```bash
./infra/local/up-platform.sh
```

`up-platform.sh` делает три шага подряд:

- пересобирает локальные image `idp-config-registry`, `grafana`, `kafka-connect`
- выполняет one-shot Alembic migrations для `Config Registry`
- поднимает полный platform slice через `docker compose up -d`

После старта сначала удобно открыть browser/UI поверхности:

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

Для ручной проверки в `MQTTX Web` создайте connection:

- protocol: `ws`
- host: `localhost`
- port: `9001`
- username/password: значения из `.env`
- subscribe topic: `idp/v1/#`

В `Kafka UI` откройте cluster `local` и topics:

- `idp.edge.configs.v1`
- `idp.telemetry.events.v1`
- `idp.source.configs.v1`
- `idp.source.connections.v1`
- `idp.agent.status.v1`
- `idp.ingestion.errors.v1`
- `idp.derived.events.v1`
- `idp.telemetry-store.dlq.v1`

`kafka-init` также создает compacted internal topics будущего Kafka Connect
runtime:

- `idp.local.kafka-connect.configs`
- `idp.local.kafka-connect.offsets`
- `idp.local.kafka-connect.status`

Быстрая проверка ClickHouse:

```bash
docker compose -f infra/local/compose.yaml --env-file .env exec clickhouse \
  sh -lc 'clickhouse-client --user "$CLICKHOUSE_USER" --password "$CLICKHOUSE_PASSWORD" --query "SELECT 1"'
```

На этом этапе `ClickHouse` в compose является storage foundation. Путь
`Kafka -> Kafka Connect -> ClickHouse` использует raw landing tables и
materialized views, которые преобразуют raw JSON в contract tables.

## Grafana -> ClickHouse read models

Grafana поставляется как локальная read-only поверхность над ClickHouse.
Datasource и dashboard создаются через provisioning, без ручной настройки в UI.

Provisioning files:

- `infra/local/grafana/provisioning/datasources/clickhouse.yaml`
- `infra/local/grafana/provisioning/dashboards/dashboards.yaml`
- `infra/local/grafana/dashboards/telemetry-overview.json`

Dashboard `Telemetry Overview` читает:

- `telemetry_latest_v1` — последние значения по точкам
- `telemetry_1m_v1` — минутные тренды
- `telemetry_1h_v1` — часовые агрегаты
- `telemetry_events_dedup_v1` и raw/contract tables — ingestion diagnostics

Быстрый seed для ручной проверки:

```bash
uv run --env-file .env idp-telemetry-store migrate up
uv run --env-file .env idp-telemetry-store load-poc telemetry-read-models \
  --rows 50000 \
  --points 100 \
  --batch-size 10000 \
  --duplicate-every 10
```

После этого откройте `http://localhost:3000`, войдите с credentials из `.env`
и выберите `Web Monitoring / Telemetry Overview`.

## ClickHouse migrations

Миграции ClickHouse хранятся рядом с CLI в
`tools/idp_telemetry_store/migrations`; fresh baseline начинается с
`0001_idp_telemetry_store_v1.sql` и применяется forward-only CLI:

Из корня репозитория:

```bash
uv run --env-file .env idp-telemetry-store migrate status
uv run --env-file .env idp-telemetry-store migrate up
```

CLI читает `CLICKHOUSE_HOST`, `CLICKHOUSE_HTTP_PORT`, `CLICKHOUSE_DATABASE`,
`CLICKHOUSE_USER`, `CLICKHOUSE_PASSWORD` и `CLICKHOUSE_SECURE` из окружения.
Metadata хранится в таблице `schema_migrations`; изменение checksum уже
примененной миграции считается fatal drift.

## Config Registry PostgreSQL migrations

`Config Registry` использует Alembic и async SQLAlchemy поверх PostgreSQL.
Локальный URL задается через `CONFIG_REGISTRY_DATABASE_URL`.

Из корня репозитория:

```bash
docker compose -f infra/local/compose.yaml --env-file .env up -d postgres
uv run --env-file .env --package idp-config-registry alembic \
  -c apps/idp_config_registry/alembic.ini upgrade head
```

Fresh Alembic baseline создает registry tables:

- `tenants`
- `assets`
- `agents`
- `sources`
- `points`

## Config Registry Outbox Worker

`idp-config-registry-outbox-worker` запускается отдельным контейнером и является
runtime worker-ом для transactional outbox:

```text
PostgreSQL config_outbox -> Config Event Publisher -> Kafka idp.edge.configs.v1
```

Alembic migrations для локального full-stack выполняет wrapper
`infra/local/up-platform.sh`, а API и worker после этого запускаются как
отдельные long-running сервисы. Worker запускает:

```bash
idp-config-registry publish-config-outbox-worker
```

По умолчанию worker опрашивает outbox раз в
`CONFIG_REGISTRY_OUTBOX_POLL_INTERVAL_SECONDS=2.0`, берет batch до
`CONFIG_REGISTRY_OUTBOX_BATCH_LIMIT=100`, ставит lease на
`CONFIG_REGISTRY_OUTBOX_LEASE_SECONDS=30` и повторяет неуспешные записи через
`CONFIG_REGISTRY_OUTBOX_RETRY_DELAY_SECONDS=30` до
`CONFIG_REGISTRY_OUTBOX_MAX_ATTEMPTS=5`.

## Kafka Connect -> ClickHouse connector

Connector config хранится в
`infra/local/kafka-connect/clickhouse-sink.telemetry-store-v1.json`.

Bootstrap из корня репозитория:

```bash
docker compose -f infra/local/compose.yaml --env-file .env up -d \
  kafka kafka-init clickhouse kafka-connect
uv run --env-file .env idp-telemetry-store migrate up
uv run --env-file .env python infra/local/kafka-connect/bootstrap_connector.py
```

MVP raw landing path:

- `value.converter=org.apache.kafka.connect.storage.StringConverter`
- `key.converter=org.apache.kafka.connect.storage.StringConverter`
- `HoistField$Value` wraps the raw Kafka value into `payload_json`
- `topic2TableMap` routes platform Kafka topics into `kafka_*_raw_v1`
  ClickHouse landing tables
- connector DLQ is `idp.telemetry-store.dlq.v1`

The connector writes only landing rows. Domain parsing and validation stay in
ClickHouse materialized views, not in Kafka Connect SMTs.

## Публикация retained config и demo telemetry

Из корня репозитория:

```bash
uv run --env-file .env --package idp-demo-stack publish-edge-demo \
  --bundle-config environments/demo-stand/edge_telemetry_agent/config.bundle.yaml
```

CLI:

- по умолчанию импортирует bundle в `Config Registry API`, вызывает
  `render-config`, а отдельный `idp-config-registry-outbox-worker` публикует
  Kafka config delivery records в `idp.edge.configs.v1`
- retained `idp.edge.agent-runtime-config.v1` и `idp.edge.source-config.v1`
  материализуются через `redpanda-connect-config-projection`
- публикует demo telemetry events
- публикует retained source connection status и agent LWT

При запущенном `redpanda-connect` эти MQTT-сообщения перекладываются в Kafka:

- telemetry -> `idp.telemetry.events.v1`
- source connection -> `idp.source.connections.v1`
- agent LWT -> `idp.agent.status.v1`
- ingestion errors -> `idp.ingestion.errors.v1`

При запущенном `redpanda-connect-config-projection` records из
`idp.edge.configs.v1` материализуются в retained MQTT topics:

- agent runtime config -> `idp/v1/agents/{agent_id}/config/agent-runtime`
- source config -> `idp/v1/agents/{agent_id}/sources/{source_id}/config`

При запущенном `redpanda-connect-source-config-snapshot` source delivery records
из `idp.edge.configs.v1` материализуются в compacted Kafka topic
`idp.source.configs.v1`. Retained MQTT source configs не являются
authoritative ingress для source snapshots.

Shim через `infra/local/scripts` тоже доступен:

```bash
uv run --env-file .env --group integration \
  python infra/local/scripts/publish_edge_demo.py \
  --bundle-config environments/demo-stand/edge_telemetry_agent/config.bundle.yaml
```

## Интеграционные тесты

```bash
uv sync --all-packages --group integration
uv run --group integration pytest \
  tests/integration/test_config_registry_kafka_publisher.py \
  tests/integration/test_config_registry_postgres.py \
  tests/integration/test_edge_agent_mqtt_publisher.py \
  tests/integration/test_edge_agent_knx_to_mqtt.py \
  tests/integration/test_kafka_to_clickhouse_storage.py \
  tests/integration/test_grafana_clickhouse.py
```

Эти тесты проверяют:

- `test_config_registry_kafka_publisher.py` проверяет
  `Config Registry -> Kafka config delivery -> retained MQTT projection`
- `test_config_registry_postgres.py` проверяет `Config Registry -> PostgreSQL`
  через Alembic и FastAPI API
- `test_edge_agent_mqtt_publisher.py` содержит два smoke-сценария:
  raw `PahoMqttPublisher -> MQTT` и CLI-path `enqueue-demo-event -> deliver-once -> MQTT`
- `test_edge_agent_knx_to_mqtt.py` проверяет lower-level edge-telemetry-agent путь:
  тестовая fixture seed-ит Kafka config delivery records, дальше проверяется
  `retained agent runtime/source config -> ObservationProcessor -> SQLite outbox -> DeliveryWorker -> MQTT -> Redpanda Connect -> Apache Kafka`
- `test_kafka_to_clickhouse_storage.py` проверяет путь
  `Kafka -> Kafka Connect -> ClickHouse raw landing -> contract table`,
  byte-for-byte сохранение Kafka value в `payload_json` и storage DLQ для
  невалидных records
- `test_grafana_clickhouse.py` проверяет путь
  `ClickHouse read models -> Grafana provisioned datasource/dashboard` и
  минимальный datasource query через Grafana API
- `local_stack` fixture поднимает только `mqtt-broker`
- `local_platform_stack` fixture поднимает `mqtt-broker`, `kafka`, `kafka-init`
  `redpanda-connect`, `redpanda-connect-config-projection` и
  `redpanda-connect-source-config-snapshot`
- `local_storage_stack` fixture поднимает `mqtt-broker`, `kafka`,
  `kafka-init`, все local Redpanda Connect pipelines, `clickhouse` и
  `kafka-connect`, применяет миграции и bootstrap connector config
- `local_grafana_clickhouse_stack` fixture поднимает только `clickhouse` и
  `grafana`, применяет миграции и seed-ит данные через load PoC в самом тесте
