# Реестр контрактов данных

Дата: 2026-05-10
Статус: working draft

`docs/contracts/` является единым source of truth для контрактов данных проекта:

- схемы сообщений и локальных структур данных
- имена MQTT topics, Kafka topics и таблиц хранения
- правила маршрутизации, дедупликации и совместимости на границах систем

После pre-production reset продуктовая граница центрального ядра называется
`Industrial Data Platform`. Contract-id, MQTT topic prefix `idp/v1`,
Kafka topic prefix `idp.*` и ClickHouse table names являются стабильным
contract surface.

## Роли артефактов

| Артефакт | Роль |
| --- | --- |
| `docs/contracts/` | Канонические контракты данных, topic/table names и boundary schemas |
| `docs/architecture/decisions.md` | Компактный register активных архитектурных решений |
| `docs/architecture/adrs/archive/` | Историческое обоснование решений и trade-off |
| `arch/likec4/` | Карта систем, контейнеров, связей и владельцев контрактов |
| `apps/*/docs/` | Руководства по использованию контрактов, примеры и runtime notes |

Полные схемы не дублируются в LikeC4 и app-документации. Если нужен полный
список полей или правил совместимости, нужно ссылаться на этот каталог.

## Разделы

- `edge-telemetry-agent/` — контракты, которыми владеет `Edge Telemetry Agent`: bootstrap config, retained agent runtime/source configs, локальное SQLite-состояние, MQTT messages и MQTT topic tree.
- `platform-ingestion/` — mapping `MQTT -> canonical Kafka record`, tenant/point enrichment и ingestion errors.
- `kafka/` — Kafka topic names, keys, retention, value schemas и consumer group conventions.
- `clickhouse/` — ClickHouse contract tables, migration-backed physical model, partition/order keys, rollups и retention policies.

## Правила версионирования

- Contract-id содержит версию, например `idp.edge.telemetry.event.v1`.
- Backward-compatible изменения допускаются внутри текущей версии только если старые consumer-ы продолжают работать.
- Breaking changes требуют новой версии контракта.
- `event_id` во всех edge/platform boundary contracts является непрозрачной непустой строкой для дедупликации, а не UUID-only типом.
- `tenant_id` в MQTT telemetry payload является claim из server-issued agent runtime config; platform ingestion обязан валидировать claim.
- `source_config_revision` является version marker для metadata source config.
