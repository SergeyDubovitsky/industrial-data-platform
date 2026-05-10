# `edge.sqlite-storage.v1`

Дата: 2026-05-02
Статус: working draft

Этот документ фиксирует логическую модель локального SQLite-хранилища
`Edge Telemetry Agent`.

## Назначение

SQLite на edge является локальным техническим состоянием агента:

- persistent cache последнего состояния точек
- очередь надежной доставки telemetry events
- счетчики sequence, попытки доставки и статусы retry
- поддержка warm restart после перезапуска агента

## Статус реализации

Сейчас в коде реализована runtime-critical часть этого контракта:

- `Delivery Outbox` реализован и используется runtime-ом
- `Point State Cache` реализован как persistent SQLite table и используется `ObservationProcessor`

Поэтому текущий runtime использует `sqlite_path` как общий local state store для
outbox и point-state cache. `schema_migrations` пока остается target contract.

SQLite не является:

- историческим архивом телеметрии
- source of truth состояния оборудования
- заменой `Telemetry Store` на базе ClickHouse

## Логические наборы данных

| Набор | Contract-id | Назначение |
| --- | --- | --- |
| `Point State Cache` | `edge.sqlite-point-state-cache.v1` | Последнее наблюденное и опубликованное состояние точки |
| `Delivery Outbox` | `edge.sqlite-outbox-record.v1` | Очередь telemetry events, ожидающих доставки или retry |

## Physical tables

| Table | Contract-id | Primary / unique keys | Статус |
| --- | --- | --- | --- |
| `point_state_cache` | `edge.sqlite-point-state-cache.v1` | primary key `(source_id, point_ref)` | implemented |
| `delivery_outbox` | `edge.sqlite-outbox-record.v1` | primary key `id`, unique `(event_id)` | implemented |
| `schema_migrations` | `edge.sqlite-storage.v1` | primary key `version` | target contract |

## Point State Cache

`Point State Cache` нужен, чтобы после restart агент не терял контекст фильтрации
изменений и sequence.

Текущее примечание: `ObservationProcessor` держит hot in-memory copy, а
persistent representation хранится в `point_state_cache`.

Минимальные обязанности:

- хранить ключ точки: `source_id + point_ref`
- хранить `last_observed_*` и `last_published_*`
- хранить `sequence` последней опубликованной telemetry event
- обновляться до постановки нового события в outbox

Physical columns:

- `source_id`
- `point_ref`
- `last_observed_at`
- `last_observed_value_json`
- `last_observed_raw`
- `last_observed_quality`
- `last_published_at`
- `last_published_value_json`
- `last_published_raw`
- `last_published_quality`
- `sequence`
- `updated_at`

## Delivery Outbox

`Delivery Outbox` нужен для retry-доставки через внешний transport.

Минимальные обязанности:

- хранить canonical telemetry event payload
- защищать от дублей по `event_id`
- поддерживать статусы `pending`, `inflight`, `sent`, `dead_letter`
- хранить `available_at`, `attempt_count`, `last_error`
- иметь lease/recovery semantics для `inflight`, чтобы события не зависали после падения delivery worker

Physical columns:

- `id`
- `event_id`
- `event_type`
- `payload_json`
- `status`
- `created_at`
- `available_at`
- `reserved_at`
- `lease_expires_at`
- `sent_at`
- `attempt_count`
- `last_error`

`reserved_at`, `lease_expires_at` и `sent_at` поддерживают lease/recovery
semantics. При старте или следующем reserve delivery worker возвращает expired
`inflight` records обратно в `pending`.

Config status, connection status и agent status messages могут публиковаться
напрямую. Они не обязаны проходить через delivery outbox, если для них не нужна
такая же retry-гарантия, как для telemetry events.

Текущее примечание: текущая реализация runtime пока публикует только telemetry
через outbox flow. Operational status messages остаются следующей фазой.
