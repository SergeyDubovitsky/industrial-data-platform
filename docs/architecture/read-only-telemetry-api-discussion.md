# Подготовка к обсуждению Read-Only Telemetry API

Дата: 2026-05-10
Статус: материал к обсуждению

Этот документ готовит ближайшее обсуждение следующего tenant-facing среза после
`Config Registry`. Он не фиксирует принятое решение; если команда подтверждает
выбранный путь, результат нужно перенести в `decisions.md` и living
source-of-truth документы.

## Рекомендуемая позиция

Следующим slice стоит выбрать read-only telemetry API для `Web Monitoring
Module` поверх существующих ClickHouse read models:

- `telemetry_latest_v1` для последних значений по точкам;
- `telemetry_events_dedup_v1` для deduplicated history.

Ownership должен быть явным:

- `Industrial Data Platform` владеет ingestion, `Telemetry Store`, ClickHouse
  contracts и read-model boundary;
- `Web Monitoring Module` владеет tenant-facing read API и будущими операторскими
  read screens;
- `Config Registry` не расширяется до telemetry/alarm API;
- `Alarm Management Module` остается отдельным slice для rules, lifecycle,
  acknowledgements, current state и notifications.

## Что уже подтверждает репозиторий

- `Config Registry` уже реализован как первый backend-срез с PostgreSQL,
  transactional outbox и config delivery path.
- `Grafana` уже является первым read-only surface `Web Monitoring Module` и
  читает ClickHouse read models.
- `telemetry_latest_v1` и `telemetry_events_dedup_v1` уже описаны в
  `docs/contracts/clickhouse/telemetry-store.v1.md` и создаются baseline
  migration.
- Integration coverage уже проверяет Kafka -> ClickHouse storage path и
  Grafana -> ClickHouse read-model surface.
- `Platform API` в глоссарии уже помечен как deprecated/ambiguous umbrella term;
  новый API нужно называть по ownership.

## Граница V1

Локальный/dev API surface для обсуждения:

- `GET /health`
- `GET /ready`
- `GET /v1/tenants/{tenant_code}/telemetry/latest`
- `GET /v1/tenants/{tenant_code}/telemetry/history`

До отдельного решения по auth/RBAC `tenant_code` остается явным local/dev API
input, а не результатом аутентифицированного контекста.

API/backoffice/domain surfaces используют public codes (`tenant_code`,
`asset_code`, `agent_code`, `source_code`, `point_code`). `tenant_id` остается
wire/storage identity для Edge/Kafka/MQTT/ClickHouse contracts и не
переименовывается этим обсуждением.

Минимальный V1 scope:

- читать latest из `telemetry_latest_v1`;
- читать history из `telemetry_events_dedup_v1`;
- возвращать только read-only telemetry data, достаточные для первого
  Web Monitoring API contract;
- не проектировать metadata joins как обязательную часть V1.

Вне V1:

- alarm lifecycle, acknowledgements, rules, notifications;
- config rollout или любые `Config Registry` writes;
- Web Monitoring UI;
- RBAC/JWT кроме явного local/dev `tenant_code`;
- write/control path в промышленный контур.

## Вопросы для встречи

- Подтверждаем ли, что следующий tenant-facing slice — telemetry read API, а не
  config rollout или alarm workflow?
- Подтверждаем ли ownership: `Web Monitoring Module` API поверх read models
  `Industrial Data Platform`?
- Достаточно ли для V1 только `latest/history`, а metadata joins, rollups и
  operator UI оставить следующими шагами?
- Принимаем ли correctness-first query views как baseline для dev/local и первого
  API contract, а production optimization откладываем до load PoC?
- Фиксируем ли результат только в `decisions.md` и living docs, или команде нужен
  отдельный ADR с durable rationale?

## Риски и развилки

- Query views удобны для первого contract и проверки semantics, но не являются
  production performance optimization.
- Явный `tenant_code` ускоряет local/dev API slice, но должен быть заменен
  authenticated tenant context после решения по IAM/RBAC. На ClickHouse/Kafka
  boundary он мапится к storage/wire `tenant_id`.
- Отдельный read API service добавляет новый backend deployable, зато не
  смешивает ownership с `Config Registry`.
- Если в V1 добавить alarm или config rollout, slice станет шире и потеряет
  проверяемость как первый Web Monitoring API boundary.

## Ожидаемый результат

После обсуждения команда должна выбрать один из вариантов:

- принять read-only telemetry API как следующий slice и обновить `decisions.md`,
  `current-state.md`, `open-questions.md` и LikeC4 при необходимости;
- оставить вопрос открытым и явно назвать blocker: API ownership, performance,
  auth/RBAC, cloud pilot scope или product priority;
- выбрать другой следующий slice и удалить/перенести candidate telemetry API в
  future backlog.
