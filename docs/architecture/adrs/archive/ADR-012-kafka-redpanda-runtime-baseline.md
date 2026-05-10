# ADR-012: Kafka/Redpanda runtime baseline

Дата: 2026-05-04
Статус: accepted

## Контекст

В архитектуре платформы есть два разных понятия, которые начали смешиваться в
документации:

- `Kafka Event Log` — логический streaming/replay слой платформы и contract
  surface из `docs/contracts/kafka/`.
- broker runtime — конкретная реализация Kafka-compatible broker-а в окружении:
  локально `Apache Kafka`, потенциально `Redpanda` или managed Kafka-compatible
  service в production.

Текущий локальный `MVP` уже использует:

- `Apache Kafka 4.2` в single-node KRaft mode как broker runtime.
- `Redpanda Connect` как connector runtime для `MQTT -> Kafka` ingestion,
  `Kafka -> MQTT retained config projection` и source config snapshot
  projection.
- `Kafka Connect` с `ClickHouse Kafka Connect Sink` для durable path
  `Kafka -> ClickHouse`.

Решение нужно, чтобы не мигрировать runtime вслепую и не создавать впечатление,
что Redpanda broker уже является обязательным production baseline.

## Decision drivers

- Не ломать уже работающий integration baseline:
  `Config Registry -> Kafka -> Redpanda Connect -> MQTT -> edge_telemetry_agent -> MQTT -> Redpanda Connect -> Kafka -> Kafka Connect -> ClickHouse`.
- Сохранить `deployment parity`: self-hosted и cloud deployment modes не должны
  расходиться по Kafka topics, message schemas, ClickHouse tables и acceptance
  semantics.
- Не заменять проверенный connector runtime кастомным кодом без необходимости.
- Оставить возможность перейти на Redpanda broker позже, если compatibility PoC
  подтвердит ценность и отсутствие регрессий.
- Разделить contract vocabulary (`Kafka Event Log`) и vendor/runtime choice
  (`Apache Kafka`, `Redpanda`, managed Kafka-compatible service).

## Решение

Для текущего `MVP` и локального development/integration stack принимается
baseline:

```text
Apache Kafka broker
  + Redpanda Connect MQTT/Kafka projections
  + Kafka Connect ClickHouse Sink
```

`Kafka Event Log` остается логическим Kafka-compatible event stream платформы.
В документации и LikeC4 он не должен означать конкретный broker product.

`Apache Kafka` остается локальной broker implementation до отдельного ADR/PoC.
Текущий single-node combined KRaft mode допустим только для development и
integration tests. Он не является production sizing или HA guidance.

`Redpanda Connect` остается connector runtime для MQTT/Kafka boundary. Его
`redpanda` input/output components считаются Kafka-compatible client components,
которые могут писать как в Apache Kafka, так и в Redpanda-compatible broker при
сохранении контрактов.

`Kafka Connect` остается runtime для `ClickHouse Kafka Connect Sink`, как
зафиксировано в `ADR-009`.

`Redpanda broker` не принимается как обязательный baseline на этом шаге. Он
остается candidate для production/self-hosted оптимизации после отдельного
compatibility PoC.

## Отклоненные варианты

| Вариант | Почему не выбираем сейчас |
| --- | --- |
| Полностью перейти на Redpanda broker | Это broker runtime migration, а не удаление лишнего компонента. Нужно проверить Kafka Connect ClickHouse Sink, Redpanda Connect projections, topic config semantics, UI/tooling и integration tests. |
| Убрать Redpanda Connect и заменить Kafka Connect MQTT connectors | Текущие Bloblang mappings уже покрывают bidirectional MQTT/Kafka projection. Kafka Connect MQTT source/sink добавит новый connector lifecycle и не упростит ClickHouse path. |
| Убрать Redpanda Connect и написать custom Python ingestion/projector services | Даст полный контроль, но придется самим реализовать retries, offset safety, backpressure, metrics, DLQ и operational lifecycle. Для MVP это лишняя ответственность. |
| Убрать Kafka Connect и писать ClickHouse через Redpanda Connect SQL sink | ADR-009 уже выбрал официальный ClickHouse Kafka Connect Sink как durable storage baseline. Generic SQL sink переносит доменную логику в connector config и ослабляет operational model. |
| Отказаться от Kafka Event Log и идти MQTT -> ClickHouse напрямую | Ломает replay, consumer decoupling, config delivery log, streaming analytics/alarm path и Kafka contracts. |

## Follow-up Redpanda broker PoC

Перед принятием Redpanda broker как runtime implementation нужно отдельной
задачей добавить compose override/profile без замены основного local stack и
проверить:

- создание всех `idp.kafka.topics.v1` topics с нужными retention/compaction
  settings;
- config delivery path:
  `Config Registry outbox -> Kafka-compatible broker -> Redpanda Connect -> retained MQTT`;
- telemetry path:
  `MQTT -> Redpanda Connect -> Kafka-compatible broker`;
- source config snapshot projection;
- `Kafka Connect ClickHouse Sink` against Redpanda broker;
- Kafka UI или Redpanda Console operational UX;
- все integration tests, которые сейчас используют Kafka bootstrap servers;
- failure modes: restart broker, restart Redpanda Connect, restart Kafka
  Connect, replay compacted config topics.

PoC не должен менять Kafka topic names, keys, value schemas, ClickHouse table
contracts или edge MQTT contracts.

## Последствия

Положительные:

- сохраняем рабочий локальный baseline без миграционного шума;
- убираем терминологическую двусмысленность между логическим event log и broker
  vendor/runtime;
- Redpanda broker остается reversibly evaluable option, а не преждевременная
  зависимость;
- Redpanda Connect и Kafka Connect остаются там, где уже дают максимальную
  пользу.

Отрицательные:

- локальный stack остается тяжелее, чем “single vendor Redpanda-only” вариант;
- в документации нужно явно различать `Redpanda Connect` и `Redpanda broker`;
- production broker selection пока не закрыт окончательно и требует отдельного
  PoC.

## Источники

- [Apache Kafka KRaft](https://kafka.apache.org/42/operations/kraft/)
- [Redpanda Kafka compatibility](https://docs.redpanda.com/current/develop/kafka-clients/)
- [Redpanda Connect redpanda input](https://docs.redpanda.com/redpanda-connect/components/inputs/redpanda/)
- [Redpanda Connect configuration](https://docs.redpanda.com/redpanda-connect/configuration/about/)
- [ClickHouse Kafka Connect Sink](https://clickhouse.com/docs/en/integrations/kafka)
