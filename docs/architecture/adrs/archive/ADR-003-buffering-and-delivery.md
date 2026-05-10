# ADR-003: Локальный `SQLite Local State Store` и надежная доставка в backend

Дата: 2026-03-20  
Статус: partially superseded by `ADR-005` and `docs/contracts/edge-telemetry-agent/`

## Контекст

Edge-сервис работает на объекте, а контур мониторинга может быть временно недоступен из-за сетевых сбоев, обслуживания или ограничений WAN. При этом потеря телеметрии нежелательна, а хранить полную историческую БД на edge-узле не требуется.

## Решение

Для доставки событий принимается схема:

- все значимые события сначала формируются в нормализованный JSON
- перед отправкой событие помещается в локальный `SQLite Delivery Outbox`
- delivery worker отправляет данные во внешний transport
- при ошибке событие остается в Delivery Outbox и повторно отправляется позже с backoff
- `SQLite Local State Store` также может хранить `Point State Cache` для warm restart и фильтрации изменений
- `SQLite` не используется как источник истины состояния оборудования и не является историческим архивом телеметрии

## Обоснование

- `SQLite` достаточно прост для одного локального процесса и не требует внешнего DBMS
- outbox-pattern позволяет разделить прием данных и нестабильность внешнего канала
- transport-specific протокол может меняться без отказа от общей outbox-модели

## Последствия

Положительные:

- collector продолжает сбор, даже если backend временно недоступен
- уменьшается риск потери событий при кратковременных сбоях
- появляется основа для гарантированной повторной отправки

Отрицательные:

- требуется контроль объема диска и retention
- появляется отдельная логика housekeeping и dead-letter политики
- для корректных retry желательно, чтобы backend поддерживал идемпотентность
- для `inflight` записей нужен lease/recovery contract, чтобы события не зависали после падения delivery worker

## Что нужно контролировать в эксплуатации

- размер Delivery Outbox и oldest pending age
- количество неудачных попыток доставки
- среднюю задержку между `ts` и `sent_at`
- случаи перехода событий в `dead_letter`

## Source of truth контрактов

Полные контракты локального SQLite-состояния вынесены в:

- `docs/contracts/edge-telemetry-agent/sqlite-storage.v1.md`
- `docs/contracts/edge-telemetry-agent/schemas/edge.sqlite-point-state-cache.v1.schema.json`
- `docs/contracts/edge-telemetry-agent/schemas/edge.sqlite-outbox-record.v1.schema.json`
