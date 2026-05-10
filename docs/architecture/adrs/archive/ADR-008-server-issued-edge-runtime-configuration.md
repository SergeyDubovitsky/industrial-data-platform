# ADR-008: Server-issued runtime-конфигурация Edge Telemetry Agent

Дата: 2026-05-02  
Статус: accepted

## Контекст

Для промышленной системы конфигурация edge-telemetry-agent должна управляться платформой
и доставляться агенту как проверяемый runtime contract:

- конфигурация объектов, агентов, источников и точек должна быть управляемой
  платформой
- `tenant_id` должен попадать в telemetry stream как часть server-issued
  agent runtime config
- AI-agent будет изменять конфигурации, поэтому нужен один проверяемый authoring
  path с JSON Schema validation, diff, revision и audit trail
- в первом этапе server UI/API для редактирования конфигурации не реализуется,
  но wire contracts должны быть совместимы с будущим `Platform Store/API`

## Решение

Целевой runtime path меняется на server-issued configuration over MQTT retained
topics.

Edge-agent локально хранит только `edge.bootstrap-config.v1`:

- `agent_id`
- MQTT endpoint и MQTT credentials/secret refs
- путь к локальному `Local State Store`
- базовые observability settings

Полная runtime-конфигурация приходит в retained MQTT topics:

- `idp/v1/agents/{agent_id}/config/agent-runtime`
- `idp/v1/agents/{agent_id}/sources/{source_id}/config`
- `idp/v1/agents/{agent_id}/status/config`

Root agent runtime config содержит `tenant_id`, `asset_id`, `agent_id`,
`config_revision` и список активных `source_id`. Source config содержит
`source_config_revision`, protocol connection settings, points,
acquisition/publish policies и metadata точек.

Явно:

- root agent runtime config не содержит полный payload конфигурации точек;
- root agent runtime config только объявляет, какие `source_id` активны и какие
  `source_config_revision` агент должен загрузить;
- полный config connection settings, defaults и points приходит отдельными
  source config payloads по `source_id`.

До внедрения backend-среза из `ADR-010` authoring source of truth — versioned
YAML config bundle в репозитории или operations bundle. Config delivery pipeline
валидирует YAML bundle по контрактам, формирует config delivery records, пишет их
в Kafka и материализует retained MQTT topics через Redpanda Connect projection.

После внедрения `ADR-010` authoring source of truth для новых конфигураций
переезжает в `Platform Store` и `Config Registry`. YAML bundle остается
только временным import/bootstrap tooling и не должен конкурировать с
PostgreSQL как runtime source of truth.

## MQTT и tenant model

Telemetry topic не содержит `tenant_id`:

```text
idp/v1/assets/{asset_id}/agents/{agent_id}/sources/{source_id}/points/{point_key}/event
```

`tenant_id` публикуется в `idp.edge.telemetry.event.v1` payload. Edge получает его из
retained agent runtime config и отправляет как платформенный claim. Platform ingestion
валидирует этот claim через MQTT auth/ACL и config registry/cache.

`source_config_revision` является version marker для metadata, использованной
при формировании telemetry event.

## Последствия

Положительные:

- edge-telemetry-agent больше не требует локального runtime registry точек
- AI-agent меняет конфигурацию через один проверяемый YAML bundle и publisher
  tool
- `tenant_id` появляется раньше, и Kafka/ClickHouse получают tenant context без
  hot-path tenant lookup
- source configs можно обновлять по `source_id`, не публикуя один большой
  retained payload на весь agent
- будущая миграция authoring path в `Platform API` не меняет edge MQTT contracts

Отрицательные:

- edge startup зависит от доступности retained config или локального последнего
  примененного snapshot
- нужен отдельный config delivery pipeline и дисциплина выпуска revisions
- retained source config может быть большим для источников с десятками тысяч
  точек
- secrets нельзя хранить plain text в retained config; нужны secret refs или
  отдельный защищенный secret flow
- retained config loader становится единственным production runtime path

## Отклоненные альтернативы

- Поддерживать второй agent runtime config path как fallback: отклонено, чтобы не
  тратить ресурсы на два runtime path и не плодить несовпадающие source of truth.
- Один retained topic со всем agent runtime config агента: отклонено как целевой
  вариант из-за размера конфигураций и слабой поддержки частичных обновлений.
- `tenant_id` в MQTT topic path: отклонено, потому что topic становится длиннее
  и раскрывает tenant context; достаточно payload claim plus ingestion validation.
- Tenant lookup только на platform-ingestion стороне: отклонено как целевая
  модель, потому что server-issued config уже содержит tenant context и позволяет
  убрать tenant lookup из hot path.

## Source of truth контрактов

Точные схемы и topic names находятся в `docs/contracts/edge-telemetry-agent/`,
`docs/contracts/platform-ingestion/`, `docs/contracts/kafka/` и
`docs/contracts/clickhouse/`.

Этот ADR является source of truth для production agent runtime configuration path
Edge Telemetry Agent.

## Текущее состояние реализации

На дату принятия ADR в коде уже реализованы:

- локальный `edge.bootstrap-config.v1`
- retained `idp.edge.agent-runtime-config.v1` / `idp.edge.source-config.v1` loader
- fail-fast сборка agent runtime config
- persistent SQLite point-state cache для warm restart/change filtering/sequence
- telemetry publishing path с `tenant_id` и `source_config_revision`

Остаются следующими шагами runtime:

- публикация `idp.edge.config.status.v1`
- публикация `idp.edge.source.connection.v1`
- публикация `idp.edge.agent.lwt.v1`
