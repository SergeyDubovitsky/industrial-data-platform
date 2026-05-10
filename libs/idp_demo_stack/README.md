# idp-demo-stack

Внутренняя библиотека для локального demo/scenario потока
`config bundle -> Config Registry API -> outbox worker -> Kafka config delivery -> retained MQTT config -> telemetry`.

Это demo/integration glue, а не production module boundary. Production
ownership остается у `Industrial Data Platform`, `Edge Telemetry Agent` и
прикладных модулей поверх них.

Содержит:

- модели и topic scope для demo-данных
- импорт demo bundle в `Config Registry API`
- генерацию Kafka config delivery records и MQTT status/telemetry сообщений
- тонкий `paho-mqtt` publisher adapter
- тонкий `confluent-kafka` publisher adapter для fallback config delivery records
- CLI для публикации demo-потока

## Запуск CLI

Предпочтительный запуск из корня репозитория:

```bash
uv run --env-file .env --package idp-demo-stack publish-edge-demo \
  --bundle-config environments/demo-stand/edge_telemetry_agent/config.bundle.yaml
```

По умолчанию config seed идет через `Config Registry API`: CLI импортирует
tenant/asset/agent/source/points из bundle, вызывает `render-config`, дальше
outbox worker публикует records в Kafka topic `idp.edge.configs.v1`.
Retained MQTT runtime/source config появляются через локальный
`redpanda-connect-config-projection`. CLI ждет retained projection перед
публикацией telemetry, чтобы локальный smoke не зависел от гонки Kafka/MQTT.

Полезные варианты:

```bash
uv run --env-file .env --package idp-demo-stack \
  publish-edge-demo --bundle-config environments/demo-stand/edge_telemetry_agent/config.bundle.yaml --count 10

uv run --env-file .env --package idp-demo-stack \
  publish-edge-demo --bundle-config environments/demo-stand/edge_telemetry_agent/config.bundle.yaml --source-id knx_main

uv run --env-file .env --package idp-demo-stack \
  publish-edge-demo --bundle-config environments/demo-stand/edge_telemetry_agent/config.bundle.yaml --retained-refresh-seconds 15

uv run --env-file .env --package idp-demo-stack \
  publish-edge-demo --bundle-config environments/demo-stand/edge_telemetry_agent/config.bundle.yaml --config-delivery mqtt

uv run --env-file .env --package idp-demo-stack \
  publish-edge-demo --bundle-config environments/demo-stand/edge_telemetry_agent/config.bundle.yaml --config-delivery kafka

uv run --env-file .env --package idp-demo-stack \
  publish-edge-demo --bundle-config environments/demo-stand/edge_telemetry_agent/config.bundle.yaml --config-projection-timeout-seconds 30
```

Совместимый shim через `infra/local/scripts` тоже поддерживается:

```bash
uv run --env-file .env --group integration \
  python infra/local/scripts/publish_edge_demo.py \
  --bundle-config environments/demo-stand/edge_telemetry_agent/config.bundle.yaml
```

## Тесты

Проверка библиотечной логики:

```bash
uv run --group integration pytest libs/idp_demo_stack/tests/test_scenario.py
```

Проверка интеграционного MQTT-контура:

```bash
uv sync --all-packages --group integration
uv run --group integration pytest \
  tests/integration/test_edge_agent_mqtt_publisher.py \
  tests/integration/test_edge_agent_knx_to_mqtt.py
```

Что именно покрывается:

- `tests/integration/test_edge_agent_mqtt_publisher.py` — raw publisher smoke и CLI-path `enqueue-demo-event -> deliver-once`
- `tests/integration/test_edge_agent_knx_to_mqtt.py` —
  lower-level edge-telemetry-agent smoke, где тестовая fixture напрямую seed-ит Kafka
  config delivery records, а дальше проверяется
  `retained config -> ObservationProcessor -> SQLite outbox -> DeliveryWorker -> MQTT -> Redpanda Connect -> Kafka`
- Grafana не входит в текущий demo/integration surface; визуализация вернется поверх `Telemetry Store`, а не напрямую поверх MQTT
