# ADR-011: Internal backoffice admin UI для Config Registry

Дата: 2026-05-03  
Статус: accepted

## Контекст

`ADR-010` фиксирует первый backend-срез платформы: `Config Registry` на
`FastAPI async + SQLAlchemy 2.x + PostgreSQL` для хранения tenants, assets,
agents, sources, points и config revisions.

Для быстрого operational workflow нужна простая админка, чтобы внутренняя команда
могла смотреть и править настройки без разработки полноценного
`Platform Frontend`. При этом изменения из админки должны запускать тот же
config revision/outbox flow, что и HTTP API.

Эта админка:

- является внутренним backoffice-инструментом
- не доступна клиентам/tenant users
- не заменяет будущий `Platform Frontend`
- не является публичным API
- не решает полноценную модель IAM, ролей и tenant self-service

## Решение

Для простейшей внутренней админки выбирается `SQLAdmin`.

Причины выбора:

- работает с `FastAPI` / `Starlette`
- работает с `SQLAlchemy` models
- поддерживает sync и async `SQLAlchemy` engine/session maker
- быстро подключается к существующему FastAPI app
- достаточно легкий для backoffice CRUD/view workflow
- не требует перехода на другой ORM

Админка подключается как infrastructure adapter внутри `apps/idp_config_registry`.
Backoffice write operations обязаны вызывать application use cases, а не менять
config tables напрямую:

```text
FastAPI app
  -> /backoffice
  -> SQLAdmin views
  -> application use cases for writes
  -> SQLAlchemy adapters / Unit of Work
  -> PostgreSQL
```

Базовый route prefix:

```text
/backoffice
```

Имя `/admin` не используется как публичный default, чтобы явно подчеркнуть
внутренний backoffice-смысл.

## Граница с clean architecture

`SQLAdmin` является UI adapter над теми же use cases, что и HTTP API.

Правило:

- backoffice ModelViews могут выполнять полный SQLAdmin CRUD напрямую через ORM
  как internal-only operator workflow
- создание tenants, assets, agents, sources, points желательно выполнять через
  уже реализованные use-case adapters, чтобы сохранить базовую validation logic
- выпуск новой `config_revision` должен идти через custom action/use case,
  который атомарно пишет config revision и `config_outbox`
- ручные CRUD-правки `config_outbox` допустимы только как internal operational
  escape hatch; штатные retry/dead-letter остаются custom actions через use cases
- админка не должна публиковать Kafka/MQTT messages напрямую

Это значит, что outbox работает с админкой только после явного render action:
direct CRUD меняет stored config state, но не выпускает новую agent runtime/source
config revision сам по себе.

Проблемный вариант:

```text
SQLAdmin direct ORM edit
  -> update sources/points
  -> no render-config use case
  -> no config_outbox record
  -> Kafka/MQTT config delivery не запускается
```

Правильный вариант:

```text
SQLAdmin form/custom action
  -> application use case
  -> PostgreSQL config revision + config_outbox в одной transaction
  -> Config Event Publisher
  -> Kafka idp.edge.configs.v1
  -> Redpanda Connect MQTT retained projection
```

## Security boundary

На первом этапе backoffice UI считается internal-only.

Минимальные правила:

- не публиковать `/backoffice` в публичный internet
- закрывать доступ network-level allowlist, VPN, local compose или reverse proxy
- не давать доступ tenant/client users
- не хранить plain text secrets в формах `connection_json`
- не считать SQLAdmin заменой будущему Keycloak/JWT/IAM ADR

Когда будет принят ADR по `Keycloak` и ролям, backoffice auth должен быть
пересмотрен и привязан к внутренним platform/operator ролям.

## Модель экранов первого инкремента

Backoffice views первого инкремента:

- `Tenant`
- `Object`
- `Agent`
- `Source`
- `Point`
- `AgentRuntimeConfigRevision`
- `SourceConfigRevision`
- `ConfigOutboxRecord`

Режимы:

- для internal backoffice включается полный SQLAdmin CRUD по всем ModelViews
- создание `Tenant` / `Object` / `Agent` / `Source` / `Point` идет через
  application use cases, где такие adapters уже реализованы
- update/delete и технические таблицы `AgentRuntimeConfigRevision`,
  `SourceConfigRevision`, `ConfigOutboxRecord` допускаются как прямой SQLAdmin
  ORM shortcut для внутренних операторов
- после прямых CRUD-правок config state оператор обязан явно вызвать
  `Render config revision`, иначе новая `config_revision` и `config_outbox`
  автоматически не появятся

Custom actions:

- `Render config revision` через операторскую страницу
  `/backoffice/render-config` с кнопкой `Обновить config state` и подсказкой о
  необходимости render после direct CRUD-правок
- `Publish config revision`
- `Retry outbox record`
- `Mark dead letter` только для internal operations и только с audit reason

Custom actions должны вызывать application use cases.

SQLAdmin CRUD считается internal operator shortcut, а не tenant-facing workflow.
Критичные side-effect операции, которые выпускают config или меняют outbox
state, остаются custom actions и должны вызывать application use cases.

## Рассмотренные варианты

| Вариант | Решение |
| --- | --- |
| `SQLAdmin` | Принят. Лучшее соответствие стеку `FastAPI + SQLAlchemy async + PostgreSQL` и минимальная цена внедрения. |
| `fastapi-admin` | Отклонено. Завязан на `TortoiseORM` и `Redis`, что конфликтует с `ADR-010`. |
| `fastapi-amis-admin` | Отклонено для первого инкремента. Мощный admin framework, но тяжелее и сильнее влияет на структуру приложения. |
| Сразу делать `Platform Frontend` | Отклонено. Это отдельный frontend/backend boundary и отдельный ADR. |
| Редактировать только через SQL/scripts | Отклонено как основной workflow. Слишком легко обойти validation/use cases/outbox. |

## Последствия

Положительные:

- быстро появляется рабочий internal UI для настройки платформы
- не нужно ждать полноценный frontend
- стек остается согласованным с `ADR-010`
- operational views для outbox и config revisions становятся видимыми

Отрицательные:

- нужно писать thin adapters для SQLAdmin forms/actions поверх use cases
- часть стандартного SQLAdmin CRUD придется отключить или переопределить
- backoffice нельзя публиковать клиентам до отдельной security/IAM модели
- часть UX будет технической, не tenant-friendly

## План реализации

1. Добавить dependency `sqladmin`.
2. Подключить SQLAdmin в `apps/idp_config_registry` на `/backoffice`.
3. Создать `admin` infrastructure module отдельно от `api/routers`.
4. Добавить CRUD ModelViews для registry/outbox/revision tables.
5. Для create registry entities использовать application use case adapters там,
   где они уже реализованы; update/delete допускаются как internal ORM shortcut.
6. Добавить custom actions, которые вызывают application use cases.
7. Оставить delete доступным только как internal backoffice operation.
8. Добавить smoke test, что `/backoffice` монтируется только в internal mode.
9. Добавить tests, что admin create для sources/points вызывает use cases и
   render action создает `config_outbox`.
10. Добавить guard test, что `SQLAdmin` не импортируется в domain/application
    слои.

## Проверки принятия

- `SQLAdmin` не импортируется в domain/application слои.
- Backoffice routes не входят в публичный tenant-facing API.
- Create-enabled registry SQLAdmin views вызывают application use cases.
- Все операции выпуска config revision проходят через application use cases.
- `config_outbox` создается только внутри транзакционного use case.
- Изменение config state через прямой CRUD в `/backoffice` требует явного
  render action для создания config revision и `config_outbox`.
- `ConfigOutboxRecord` может редактироваться через internal CRUD, но
  retry/dead-letter operational paths должны оставаться custom actions через
  application use cases.
- Delete actions доступны только в internal backoffice и не считаются
  tenant-facing workflow.

## Источники

- `SQLAdmin`: https://github.com/smithyhq/sqladmin
- `SQLAdmin` документация: https://smithyhq.github.io/sqladmin/
- `fastapi-admin`: https://github.com/fastapi-admin/fastapi-admin
- `fastapi-amis-admin`: https://docs.gh.amis.work/
