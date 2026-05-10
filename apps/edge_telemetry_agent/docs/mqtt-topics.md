# MQTT Topics и Publish Guide

Дата: 2026-05-02
Статус: guide

Этот документ объясняет, как `Edge Telemetry Agent` публикует сообщения в MQTT.
Канонический source of truth для topic templates, QoS/retain/expiry и payload
schemas находится в:

- [`docs/contracts/edge-telemetry-agent/mqtt-topic-tree.v1.md`](../../../docs/contracts/edge-telemetry-agent/mqtt-topic-tree.v1.md)
- [`docs/contracts/edge-telemetry-agent/schemas/`](../../../docs/contracts/edge-telemetry-agent/schemas/)

## Message contracts

| Message contract | Назначение |
| --- | --- |
| `idp.edge.agent-runtime-config.v1` | Retained root agent runtime config агента |
| `idp.edge.source-config.v1` | Retained source config по `source_id` |
| `idp.edge.config.status.v1` | Target contract для retained status применения конфигурации |
| `idp.edge.telemetry.event.v1` | Реализованный thin telemetry payload; identity берется из MQTT topic path |
| `idp.edge.source.connection.v1` | Target contract для retained status southbound source |
| `idp.edge.agent.lwt.v1` | Target contract для retained LWT/status MQTT publisher агента |

## Routing principles

- Telemetry topic содержит `asset_id`, `agent_id`, `source_id` и `point_key`.
- Telemetry payload содержит `tenant_id` claim и не дублирует routing identity или стабильную point metadata.
- Retained operational status payloads содержат `tenant_id`, чтобы ingestion не
  зависел от порядка replay retained config/status topics.
- Source config публикуется retained record-ом на каждый `source_id`.
- Per-point retained `state` topic не используется.
- Backend/ingestion должен считать `event_id` ключом дедупликации, но не должен полагаться на конкретный формат `event_id`.

## Совместимость

- При изменении wire payload создается новый `message_type`, например `idp.edge.telemetry.event.v2`.
- Текущий MQTT payload поддерживает только scalar values: `boolean`, `number`, `string`, `null`.
- Complex protocol values для будущих источников должны получить отдельный versioned contract.

## Локальная проверка

Текущий локальный dev-контур использует `MQTT broker` и читает те же topics,
которые описаны в registry. Для ручной генерации demo telemetry
используйте команды из корневого `README.md`.

На текущем этапе локальные проверки и integration tests покрывают именно
retained config + telemetry flow. Operational status topics в runtime пока не
входят в реализованный baseline.
