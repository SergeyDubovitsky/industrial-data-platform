# Конфигурация edge agent

Рабочий путь runtime-конфигурации теперь один:

1. локальный `edge.bootstrap-config.v1`
2. retained `idp.edge.agent-runtime-config.v1`
3. retained `idp.edge.source-config.v1`

Этот каталог хранит только developer examples:

- `examples/bootstrap.example.yaml` — минимальный локальный bootstrap
- `examples/config.bundle.example.yaml` — authoring bundle, из которого demo/tooling
  импортирует настройки в `Config Registry API`

`edge_telemetry_agent` читает локально только bootstrap-файл. Bundle не загружается
напрямую рантаймом: он нужен для demo и интеграционных сценариев. В
production-like local demo CLI импортирует bundle в `Config Registry API`,
после чего outbox worker публикует Kafka config delivery records, а retained
config материализуется Redpanda Connect projection.

Текущие integration-тесты используют именно этот split:

- временный локальный `bootstrap.yaml`, созданный в `tmp_path` на время теста
- retained agent runtime/source config, материализованный из Kafka delivery records
  по данным `config.bundle.yaml`
- затем `edge_telemetry_agent` валидирует и использует уже собранный MQTT-side runtime state

Для локального запуска examples могут использовать placeholders вида `${VAR}`.
YAML/JSON документы подхватывают значения из уже переданного окружения. Для
запуска из monorepo используйте `uv run --env-file .env`.

Fail-fast проверки нового потока:

- `bootstrap.agent_id` должен совпадать с `runtime_config.agent_id`
- для каждого `source_id` из retained agent runtime config должен существовать retained source config
- `tenant_id`, `asset_id`, `agent_id` и `config_revision` в source config должны совпадать с root agent runtime config
- `source_config_revision` и `enabled` в source config должны совпадать с root agent runtime config
- `point_key` должен быть percent-encoded представлением `point_ref`
- `change_threshold` допускается только для числовых значений

Полные контракты runtime-конфигурации, локального SQLite state и MQTT messages
зафиксированы в `docs/contracts/edge-telemetry-agent/`.
