# `idp.kafka.topics.v1`

Дата: 2026-05-10
Статус: working draft

Этот контракт фиксирует Kafka-compatible topics `Industrial Data Platform`.
`Kafka Event Log` является логическим Kafka-compatible event stream, а не
конкретным broker product. Локальный integration slice использует
`Apache Kafka` как broker runtime и `Redpanda Connect` как connector pipeline
`MQTT -> Kafka`. `Redpanda broker` остается candidate для production/self-hosted
runtime после compatibility PoC. Активное broker/runtime решение сведено в
`docs/architecture/decisions.md`.

`idp.*` является стабильным wire-prefix текущего pre-production baseline.
Совместимость со старыми локальными topics не поддерживается.

## Topics

| Topic | Value schema | Kafka key | Retention | Compaction | Producers | Consumers |
| --- | --- | --- | --- | --- | --- | --- |
| `idp.telemetry.events.v1` | `idp.telemetry.event.v1` | `{tenant_id}|{asset_id}|{source_id}|{point_key}` | `7d` | no | Redpanda Connect | `telemetry-store-writer.v1`, `streaming-analytics.v1`, `alarm-rule-engine.v1` |
| `idp.edge.configs.v1` | `idp.edge.config.delivery.v1` | `{tenant_id}|{asset_id}|{agent_id}|{config_scope}` | `30d` | yes | Config Event Publisher | Redpanda Connect MQTT projection, Source Config Snapshot Projector, operations tooling |
| `idp.source.configs.v1` | `idp.source.config.v1` | `{tenant_id}|{asset_id}|{agent_id}|{source_id}` | `30d` | yes | Source Config Snapshot Projector from `idp.edge.configs.v1` | `telemetry-store-writer.v1`, `streaming-analytics.v1`, ingestion registry/cache |
| `idp.source.connections.v1` | `idp.source.connection.v1` | `{tenant_id}|{asset_id}|{agent_id}|{source_id}` | `30d` | yes | Redpanda Connect | `telemetry-store-writer.v1`, `alarm-rule-engine.v1` |
| `idp.agent.status.v1` | `idp.agent.status.v1` | `{tenant_id}|{asset_id}|{agent_id}` | `30d` | yes | Redpanda Connect | `telemetry-store-writer.v1`, `alarm-rule-engine.v1` |
| `idp.ingestion.errors.v1` | `idp.ingestion.error.v1` | `{asset_id}|{agent_id}|{source_id}|{message_kind}` | `30d` | no | Redpanda Connect | operations tooling |
| `idp.derived.events.v1` | `idp.derived.event.v1` | `{tenant_id}|{asset_id}|{rule_or_metric_id}` | `7d` | no | Streaming Analytics | `telemetry-store-writer.v1`, `alarm-rule-engine.v1` |

## Consumer groups

| Consumer group | Reads | Writes / side effects |
| --- | --- | --- |
| `telemetry-store-writer.v1` | telemetry, source config, source connection, agent status, derived events | ClickHouse `Telemetry Store` tables |
| `edge-config-mqtt-projector.v1` | edge config delivery records | MQTT retained agent runtime/source config topics |
| `source-config-snapshot-projector.v1` | edge config delivery records | `idp.source.configs.v1` source config snapshots |
| `streaming-analytics.v1` | telemetry, source config | derived events, rollups and aggregates |
| `alarm-rule-engine.v1` | telemetry, source connection, agent status, derived events | alarm history, current alarm workflow state and notifications |

## Common rules

- `tenant_id` обязателен во всех normal platform topics.
- `tenant_id` присутствует в MQTT telemetry payload как edge claim из server-issued agent runtime config и валидируется ingestion-слоем.
- `idp.edge.configs.v1` является Kafka-first delivery log для edge agent runtime/source configs; edge-telemetry-agent не читает Kafka, а получает MQTT retained projection.
- `idp.edge.configs.v1` records обязаны содержать `config_scope`: `agent_runtime` для root agent runtime config или `source:{source_id}` для source config.
- `idp.edge.configs.v1` records обязаны содержать `target_mqtt_topic`, `mqtt_retain=true`, `mqtt_qos=1`, `operation` и `payload`, чтобы MQTT retained projection была детерминированной и восстанавливаемой replay-ем Kafka topic.
- `idp.source.configs.v1` строится только из `idp.edge.configs.v1`; retained MQTT source configs не являются authoritative Kafka ingress для source config snapshots.
- `event_id` является непрозрачной непустой строкой; Kafka consumers не должны требовать UUID-only формат.
- `idempotency_key` обязателен для records, которые пишутся в ClickHouse.
- `idp.edge.agent-runtime-config.v1` не зеркалится из retained MQTT обратно в Kafka; agent runtime/source configs попадают в Kafka только как `idp.edge.config.delivery.v1` records из Config Registry/YAML delivery path.
- `idp.edge.config.status.v1` не зеркалится в Kafka topics этого контракта `v1`; он остается retained MQTT/status contract для bootstrap/operations до отдельного runtime-инкремента.
- Topic names и key templates являются breaking contract surface; изменение требует новой версии topic.
- Compacted status/config topics хранят latest state по key, но не заменяют ClickHouse snapshots и history.
