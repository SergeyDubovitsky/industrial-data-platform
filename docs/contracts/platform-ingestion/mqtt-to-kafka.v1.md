# `idp.ingestion.mqtt-to-kafka.v1`

Дата: 2026-05-10
Статус: working draft

Этот контракт фиксирует преобразование MQTT edge boundary в canonical Kafka
records для `Industrial Data Platform`.

Kafka topics и message types используют `idp.*` как стабильный wire contract.

## Input

Ingestion pipeline принимает:

- MQTT topic path из `idp.edge.mqtt.topic-tree.v1`
- MQTT payload contracts `idp.edge.telemetry.event.v1`, `idp.edge.source.connection.v1`,
  `idp.edge.agent.lwt.v1`
- config registry/cache для проверки `tenant_id`, `source_config_revision` и
  `point_id`; authoritative registry/cache строится из `idp.source.configs.v1`
  и/или `Platform Store`

`tenant_id` публикуется edge-telemetry-agent-ом в MQTT payload как claim из retained
agent runtime config. Ingestion не берет tenant из topic path и обязан валидировать
claim через MQTT auth/ACL и config registry/cache.

`idp.edge.agent-runtime-config.v1` и `idp.edge.config.status.v1` не входят в Kafka
surface этого контракта `v1`. Они остаются retained MQTT contracts для
bootstrap/operational lifecycle edge-telemetry-agent и должны быть исключены фильтром
подписки или routing rules до стадии Kafka mapping, а не считаться ingestion
error.

## Routing context

Из MQTT topic path извлекаются:

| Поле | Источник |
| --- | --- |
| `asset_id` | topic segment `assets/{asset_id}` |
| `agent_id` | topic segment `agents/{agent_id}` |
| `source_id` | topic segment `sources/{source_id}` для telemetry/source status topics |
| `point_key` | topic segment `points/{point_key}` для telemetry events |
| `message_kind` | suffix `event`, `status/connection`, `status/lwt`; retained config suffixes исключаются routing rules до Kafka mapping |

Все path identifiers должны соответствовать edge MQTT contract. Topic, который
не матчится на известный template, отправляется в
`idp.ingestion.errors.v1`.

## Enrichment

Tenant validation:

- input field: `tenant_id` из `idp.edge.telemetry.event.v1`
- validation key: `tenant_id + asset_id + agent_id + source_id`
- validation source: config registry/cache, сформированный из `idp.source.configs.v1` и/или `Platform Store`
- output field: `tenant_id` сохраняется без изменения

Point enrichment для telemetry events:

- lookup key: `tenant_id + asset_id + source_id + point_key`
- lookup source: config registry/cache
- output fields: `point_id`, `point_ref`, `source_type`, metadata fields
- MVP default до появления Platform Registry: `point_id` формируется
  детерминированно как `{tenant_id}|{asset_id}|{source_id}|{point_key}`.
  Этот fallback является provisional compatibility layer и должен быть заменен
  на stable registry id после появления Platform Store/API.

Source config enrichment:

- `idp.source.configs.v1` обновляет config registry/cache candidate state
- `source_config_revision` используется как версия source config
- telemetry event с неизвестным `source_config_revision` не пишется в telemetry topic
  и уходит в ingestion error topic

Retained `idp.edge.agent-runtime-config.v1` / `idp.edge.source-config.v1` topics являются
delivery projection для edge-telemetry-agent и не являются authoritative MQTT ingress для
`idp.source.configs.v1`.

Local `Redpanda Connect` может использовать retained `idp.edge.source-config.v1`
как неавторитетный warmup для ephemeral enrichment cache, но не должен
публиковать из него `idp.source.configs.v1`; canonical source snapshots строит
только `Source Config Snapshot Projector` из `idp.edge.configs.v1`.

## Output records

| Input | Kafka topic | Kafka value schema |
| --- | --- | --- |
| `idp.edge.telemetry.event.v1` | `idp.telemetry.events.v1` | `idp.telemetry.event.v1` |
| `idp.edge.source.connection.v1` | `idp.source.connections.v1` | `idp.source.connection.v1` |
| `idp.edge.agent.lwt.v1` | `idp.agent.status.v1` | `idp.agent.status.v1` |
| invalid / unresolved input | `idp.ingestion.errors.v1` | `idp.ingestion.error.v1` |

Telemetry idempotency key:

```text
{tenant_id}|{asset_id}|{agent_id}|{event_id}
```

Telemetry Kafka key:

```text
{tenant_id}|{asset_id}|{source_id}|{point_key}
```

Этот key сохраняет ordering по одной точке внутри Kafka partition. `event_id`
остается непрозрачной непустой строкой и не интерпретируется как UUID.

## Error handling

Запись не попадает в normal Kafka topic и отправляется в
`idp.ingestion.errors.v1`, если:

- MQTT topic не соответствует `idp.edge.mqtt.topic-tree.v1`
- payload не соответствует заявленной schema
- `tenant_id` claim не совпадает с MQTT auth/ACL или config registry/cache
- point lookup отсутствует или неоднозначен для telemetry event
- `source_config_revision` отсутствует в registry/cache для telemetry event
- `point_key` из topic отсутствует в source config

Error record должен содержать исходный topic, `message_type`, reason code,
ingestion timestamp и raw payload snapshot, если snapshot не нарушает политики
безопасности.

## Compatibility

- Добавление новых optional fields в canonical Kafka records допускается в рамках
  `v1`, если старые consumers продолжают работать.
- Изменение Kafka key, topic name, idempotency key или обязательных fields
  требует нового contract-id.
