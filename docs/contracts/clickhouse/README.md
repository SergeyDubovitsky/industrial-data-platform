# ClickHouse Contracts

Дата: 2026-05-10
Статус: working draft

Раздел фиксирует ClickHouse table names, contract tables, migration-backed
physical model, engines, partition/order keys, materialized views, rollups и
retention policies.

ClickHouse `Telemetry Store` относится к `Industrial Data Platform`; таблицы
не переименовываются при выделении `Web Monitoring Module` и
`Alarm Management Module`.

## Контракты

| Contract-id | Файл | Назначение |
| --- | --- | --- |
| `idp.telemetry-store.clickhouse.telemetry-store.v1` | `telemetry-store.v1.md` | Таблицы `Telemetry Store`, migration-backed physical model, keys и retention |
