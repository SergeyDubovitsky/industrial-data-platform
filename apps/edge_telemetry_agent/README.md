# Edge Agent

Workspace member for the edge telemetry runtime.

## Commands

```bash
test -f .env || cp .env.example .env
uv sync
uv run --package edge-telemetry-agent pytest apps/edge_telemetry_agent/tests
uv run --package edge-telemetry-agent edge-telemetry-agent --help
uv run --env-file .env --package edge-telemetry-agent edge-telemetry-agent \
  check-config --bootstrap-config environments/demo-stand/edge_telemetry_agent/bootstrap.yaml
uv run --env-file .env --package edge-telemetry-agent edge-telemetry-agent \
  show-config --bootstrap-config environments/demo-stand/edge_telemetry_agent/bootstrap.yaml --format json
uv run --env-file .env --package edge-telemetry-agent edge-telemetry-agent \
  enqueue-demo-event --bootstrap-config environments/demo-stand/edge_telemetry_agent/bootstrap.yaml
uv run --env-file .env --package edge-telemetry-agent edge-telemetry-agent \
  deliver-once --bootstrap-config environments/demo-stand/edge_telemetry_agent/bootstrap.yaml
uv run --env-file .env --package edge-telemetry-agent edge-telemetry-agent \
  run --bootstrap-config environments/demo-stand/edge_telemetry_agent/bootstrap.yaml
```

## Integration Tests

```bash
uv sync --all-packages --group integration
uv run --group integration pytest \
  tests/integration/test_edge_agent_mqtt_publisher.py \
  tests/integration/test_edge_agent_knx_to_mqtt.py
```

Текущее покрытие:

- `test_edge_agent_mqtt_publisher.py` — transport smoke и CLI-сценарий `enqueue-demo-event -> deliver-once`
- `test_edge_agent_knx_to_mqtt.py` — реальный `ObservationProcessor -> SQLite outbox -> DeliveryWorker -> MQTT` для demo `knx_main`
- `apps/edge_telemetry_agent/tests/test_runtime.py` — async runtime path, где
  southbound observations проходят через `ObservationProcessor`, SQLite outbox
  boundary и `DeliveryWorker`; command-точки подавляются до telemetry publish.
- retained agent runtime/source config в edge-telemetry-agent integration fixture seed-ится
  напрямую через Kafka config delivery records, чтобы изолировать runtime агента.
  Production-like local demo seed идет через
  `Config Registry API -> outbox worker -> Kafka -> retained MQTT projection`.
- Для synthetic local smoke `apps/knx_source_emulator` потребляет
  `idp_synthetic_config` и отдает KNX-like события по `connection.mode=synthetic`;
  MQTT telemetry при этом публикует только настоящий `edge_telemetry_agent`.

## Runtime Assets

- `config/examples/bootstrap.example.yaml` — локальный bootstrap example
- `config/examples/config.bundle.example.yaml` — authoring bundle example для
  demo import в `Config Registry API`
- `../../docs/contracts/edge-telemetry-agent/` — canonical edge contracts, MQTT topic tree, and payload schemas
- `docs/data-contracts.md` — guide по edge runtime dataflow, config model, and contract usage
- `docs/mqtt-topics.md` — guide по MQTT publish rules и ссылкам на canonical topic tree
- `../../environments/demo-stand/edge_telemetry_agent/` — demo-stand bootstrap и config bundle
- `../../infra/local/` — local `MQTT broker` stack for development and integration tests
