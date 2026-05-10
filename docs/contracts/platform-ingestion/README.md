# Platform Ingestion Contracts

Дата: 2026-05-10
Статус: working draft

Раздел фиксирует контракты преобразования:

```text
MQTT topic + MQTT payload + retained source config
  -> canonical Kafka record
  -> downstream consumers
```

Эти контракты принадлежат `Industrial Data Platform`. `idp.*` message types и
topics являются стабильным wire surface после pre-production reset.

## Контракты

| Contract-id | Файл | Назначение |
| --- | --- | --- |
| `idp.ingestion.mqtt-to-kafka.v1` | `mqtt-to-kafka.v1.md` | Mapping MQTT edge boundary в canonical Kafka records |
