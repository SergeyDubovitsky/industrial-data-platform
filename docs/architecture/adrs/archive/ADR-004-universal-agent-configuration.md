# ADR-004: Идентичность Edge Telemetry Agent

Дата: 2026-03-28  
Статус: accepted

## Контекст

Edge agent должен устанавливаться рядом с объектами автоматизации. Таких
объектов и агентов может быть много, поэтому данные должны иметь стабильную
идентичность на уровне tenant, asset, agent, source и point.

Конфигурационная модель runtime определяется `ADR-008`. Этот ADR фиксирует
только правила идентичности, которые остаются обязательными для edge-telemetry-agent,
MQTT, Kafka и ClickHouse contracts.

## Решение

Идентичность разделяется на уровни:

- `tenant_id` — клиент/tenant платформы, приходит в edge-telemetry-agent из
  server-issued agent runtime config
- `asset_id` — бизнес-идентификатор объекта автоматизации в системе мониторинга
- `agent_id` — технический идентификатор экземпляра edge-telemetry-agent
- `source_id` — идентификатор конкретного protocol source внутри agent
- `point_key` — MQTT-safe ключ точки внутри source
- `point_ref` — исходный protocol reference точки, например KNX group address,
  Modbus register или OPC UA node id

`agent_id` сохраняется как обязательная runtime identity. Он не должен
вычисляться из hostname, MAC-адреса или имени compose service.

`source_id` используется в конфигурации, валидации, MQTT topics, Kafka keys и
ClickHouse storage как идентификатор конкретного подключения, а не только типа
протокола.

## Правила

- `tenant_id` должен присутствовать в server-issued agent runtime/source config и
  telemetry payload.
- `asset_id`, `agent_id` и `source_id` должны соответствовать MQTT path-id
  contract.
- `point_key` должен быть одним MQTT topic segment и строиться обратимо из
  `point_ref`.
- `point_ref` должен быть уникален в рамках одного `source_id`.
- Целевой `point_id` на стороне платформы строится и хранится в Platform
  Registry / Platform Store. До появления Platform Registry ingestion pipeline
  может использовать provisional deterministic fallback
  `{tenant_id}|{asset_id}|{source_id}|{point_key}`.
- `event_id` является непрозрачной непустой строкой для дедупликации и не
  требует UUID-only формата.

## Обоснование

- Разделение `asset_id`, `agent_id`, `source_id` и `point_key` защищает от
  конфликтов при масштабировании объектов, агентов и protocol sources.
- `source_id + point_ref` дает универсальную ключевую модель для KNX, Modbus,
  OPC UA, DB и будущих источников.
- `tenant_id` в payload позволяет platform ingestion валидировать tenant claim
  до записи в Kafka и ClickHouse.
- `point_key` отделяет MQTT routing от protocol-specific identifiers, которые
  могут содержать `/`, пробелы или другие небезопасные для topic path символы.

## Source Of Truth

- Agent runtime/source configuration contracts: `docs/contracts/edge-telemetry-agent/`
- MQTT topic tree: `docs/contracts/edge-telemetry-agent/mqtt-topic-tree.v1.md`
- Platform ingestion mapping: `docs/contracts/platform-ingestion/`
- Storage model: `docs/contracts/clickhouse/`
