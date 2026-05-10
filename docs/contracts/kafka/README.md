# Kafka Contracts

Дата: 2026-05-10
Статус: working draft

Раздел фиксирует Kafka topic names, keys, value schemas, retention,
partitioning и consumer group conventions `Industrial Data Platform`.

Префикс `idp.*` является стабильным wire-prefix текущего pre-production
baseline. Topic names являются breaking contract surface после этого reset.

## Контракты

| Contract-id | Файл | Назначение |
| --- | --- | --- |
| `idp.kafka.topics.v1` | `topics.v1.md` | Topic names, keys, retention и consumer groups |
| `idp.telemetry.event.v1` | `schemas/idp.telemetry.event.v1.schema.json` | Canonical telemetry event |
| `idp.edge.config.delivery.v1` | `schemas/idp.edge.config.delivery.v1.schema.json` | Kafka delivery envelope для MQTT retained agent runtime/source config projection |
| `idp.source.config.v1` | `schemas/idp.source.config.v1.schema.json` | Source config snapshot |
| `idp.source.connection.v1` | `schemas/idp.source.connection.v1.schema.json` | Source connection status event |
| `idp.agent.status.v1` | `schemas/idp.agent.status.v1.schema.json` | Agent LWT/status event |
| `idp.ingestion.error.v1` | `schemas/idp.ingestion.error.v1.schema.json` | Ingestion DLQ/error record |
| `idp.derived.event.v1` | `schemas/idp.derived.event.v1.schema.json` | Derived event from Streaming Analytics |
