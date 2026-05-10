# Контракты Edge Telemetry Agent

Дата: 2026-05-02
Статус: working draft

Этот раздел фиксирует контракты данных, которыми владеет `Edge Telemetry Agent`.
Существующие документы в `apps/edge_telemetry_agent/docs/` остаются guide-ами и примерами,
а полные схемы и имена topics находятся здесь.

Production-модель server-issued config: edge-telemetry-agent стартует с минимальным
`edge.bootstrap-config.v1`, получает retained `idp.edge.agent-runtime-config.v1` и
`idp.edge.source-config.v1` из MQTT и публикует telemetry с `tenant_id` из
server-issued config.

## Статус реализации

На текущем этапе в коде уже реализовано:

- bootstrap-конфигурация агента
- загрузка retained agent runtime/source config из MQTT
- canonical telemetry event
- persistent `SQLite Point State Cache`
- SQLite delivery outbox
- публикация `idp.edge.telemetry.event.v1`

Пока еще не реализовано в runtime, но уже зафиксировано как target contract:

- публикация `idp.edge.config.status.v1`
- публикация `idp.edge.source.connection.v1`
- публикация `idp.edge.agent.lwt.v1`
- `Topic Alias` optimization в MQTT publisher

## Поток данных

```text
Observation
  -> Bootstrap Config
  -> Retained Agent Runtime Config
  -> Retained Source Configs by source_id
  -> Protocol Decoder / Normalizer
  -> In-memory Last Value Cache
  -> SQLite Point State Cache
  -> Change Filter
  -> SQLite Delivery Outbox
  -> Delivery Worker
  -> MQTT topic tree
```

## Контракты

| Contract-id | Файл | Назначение |
| --- | --- | --- |
| `edge.bootstrap-config.v1` | `schemas/edge.bootstrap-config.v1.schema.json` | Минимальная локальная конфигурация запуска: `agent_id`, MQTT endpoint, local storage и observability |
| `idp.edge.agent-runtime-config.v1` | `schemas/idp.edge.agent-runtime-config.v1.schema.json` | Retained root agent runtime config агента: `tenant_id`, `asset_id`, `agent_id`, `config_revision`, список `sources` |
| `idp.edge.source-config.v1` | `schemas/idp.edge.source-config.v1.schema.json` | Retained source config по `source_id`: connection, points, acquisition/publish policies |
| `idp.edge.config.status.v1` | `schemas/idp.edge.config.status.v1.schema.json` | Retained статус применения конфигурации агентом |
| `edge.telemetry-event.v1` | `schemas/edge.telemetry-event.v1.schema.json` | Каноническое telemetry event внутри edge-telemetry-agent до MQTT wire transform |
| `edge.sqlite-point-state-cache.v1` | `schemas/edge.sqlite-point-state-cache.v1.schema.json` | Persistent cache последнего состояния точки в SQLite |
| `edge.sqlite-outbox-record.v1` | `schemas/edge.sqlite-outbox-record.v1.schema.json` | Запись очереди надежной доставки в SQLite |
| `idp.edge.telemetry.event.v1` | `schemas/idp.edge.telemetry.event.v1.schema.json` | Thin MQTT payload для telemetry event |
| `idp.edge.source.connection.v1` | `schemas/idp.edge.source.connection.v1.schema.json` | Retained status сообщения southbound source |
| `idp.edge.agent.lwt.v1` | `schemas/idp.edge.agent.lwt.v1.schema.json` | Retained LWT/status сообщения MQTT publisher агента |
| `idp.edge.mqtt.topic-tree.v1` | `mqtt-topic-tree.v1.md` | MQTT topic templates, routing identity, QoS, retain и expiry |

## Reference Notes

- [`config-revision-model.md`](./config-revision-model.md) — как связаны
  `AgentRuntimeConfigRevision`, `SourceConfigRevision`, `config_revision` и
  `source_config_revision`; как они формируются и передаются по контуру

## Основные правила

- `event_id` — непрозрачная непустая строка для дедупликации. Рекомендуемый production generator: `UUIDv7` или `ULID`; consumer не должен зависеть от конкретного формата.
- `tenant_id` приходит в edge-telemetry-agent из `idp.edge.agent-runtime-config.v1` и публикуется в `idp.edge.telemetry.event.v1` payload как claim; ingestion обязан валидировать claim.
- `tenant_id` также обязателен в retained operational status payloads
  `idp.edge.source.connection.v1` и `idp.edge.agent.lwt.v1`, чтобы ingestion мог писать
  Kafka status records без зависимости от порядка replay retained config topics.
- `source_config_revision` связывает telemetry event с retained source config, по которому backend выполняет enrichment.
- `asset_id`, `agent_id`, `source_id` и segments `topic_root` должны соответствовать `mqtt_path_id`: `^[a-z0-9][a-z0-9_-]{0,127}$`.
- `point_key` — обратимое percent-encoding от `point_ref`, пригодное для MQTT topic path.
- `command` points не публикуются как production telemetry; `publish.enabled`
  не должен использоваться как override для control/write-path сигналов.
- SQLite на edge хранит техническое состояние агента, а не исторический архив телеметрии.
- `SQLite Point State Cache` поддерживает warm restart, фильтрацию изменений и восстановление sequence.
- `SQLite Delivery Outbox` нужен для надежной retry-доставки telemetry events.
- Agent runtime/source config приходит в retained MQTT topics как platform projection из Kafka config delivery records.
- В текущей реализации edge-telemetry-agent публикует telemetry; config status и operational status остаются следующей фазой runtime.
- YAML config bundle остается versioned import/bootstrap path и не конкурирует с `Config Registry`/`Platform Store` как source of truth; wire contracts при этом не меняются.
