# idp-config-registry

Первый backend-срез `Industrial Data Platform Config Registry` для
tenants/assets/agents/sources/points и Kafka-first config delivery flow.

Package name, import path, CLI entrypoint и Docker service являются
stable identifiers: `idp_config_registry`, `idp-config-registry`,
`idp-config-registry` / `idp-config-registry-outbox-worker`.

Текущий инкремент реализует минимальный clean architecture baseline:

- FastAPI app factory
- domain entities/value objects для registry-модели
- application use cases и repository/unit-of-work protocols
- render use case для `idp.edge.agent-runtime-config.v1` и
  `idp.edge.source-config.v1` с JSON Schema validation
- persistence для rendered `agent_runtime_config_revisions` и
  `source_config_revisions`
- transactional `config_outbox` pending records для Kafka-first edge config
  delivery
- outbox lease workflow и `Config Event Publisher` boundary:
  `reserve -> publish -> mark_published/mark_retry/mark_dead_letter`
- `confluent-kafka` adapter для записи config delivery records в
  `idp.edge.configs.v1`
- long-running CLI worker `publish-config-outbox-worker` для отдельного
  контейнера outbox worker-а
- internal backoffice UI на `/backoffice` в `internal_mode`
- local Redpanda Connect projection
  `idp.edge.configs.v1 -> MQTT retained agent runtime/source config topics`
- временный in-memory adapter для unit/API smoke-тестов
- PostgreSQL adapter для `tenants`, `assets`, `agents`, `sources` и `points`
- local Docker image для `idp-config-registry` и
  `idp-config-registry-outbox-worker`
- fresh Alembic baseline migration для registry tables:
  `tenants`, `assets`, `agents`, `sources`, `points`
- `agent_runtime_config_revisions`, `source_config_revisions`
- `config_outbox`
- endpoints `GET /health`, `GET /ready`, `POST /tenants`, `GET /tenants`,
  `POST /tenants/{tenant_id}/assets`, `GET /tenants/{tenant_id}/assets`,
  `POST /tenants/{tenant_id}/assets/{asset_id}/agents`,
  `GET /tenants/{tenant_id}/assets/{asset_id}/agents`,
  `POST /tenants/{tenant_id}/assets/{asset_id}/agents/{agent_id}/render-config`,
  `POST /tenants/{tenant_id}/assets/{asset_id}/agents/{agent_id}/sources`,
  `GET /tenants/{tenant_id}/assets/{asset_id}/agents/{agent_id}/sources`,
  `POST /tenants/{tenant_id}/assets/{asset_id}/agents/{agent_id}/sources/{source_id}/points`,
  `GET /tenants/{tenant_id}/assets/{asset_id}/agents/{agent_id}/sources/{source_id}/points`

CLI/runtime упаковка publisher-а и local Redpanda Connect
`Kafka -> MQTT retained` projection реализованы как первый delivery baseline
для Config Registry.

```bash
uv run --package idp-config-registry pytest apps/idp_config_registry/tests
uv run --package idp-config-registry idp-config-registry
```

PostgreSQL migrations:

```bash
uv run --env-file .env --package idp-config-registry alembic \
  -c apps/idp_config_registry/alembic.ini upgrade head
```

Для запуска API с PostgreSQL задайте `CONFIG_REGISTRY_DATABASE_URL`, например:

```bash
CONFIG_REGISTRY_DATABASE_URL=postgresql+asyncpg://idp:change-me-local-postgres@localhost:5432/idp_config_registry \
  uv run --package idp-config-registry idp-config-registry
```

Если `CONFIG_REGISTRY_INTERNAL_MODE=true` и API запущен с PostgreSQL-backed
`CONFIG_REGISTRY_DATABASE_URL`, дополнительно монтируется internal
`/backoffice`. В админке `details` страницы остаются полным raw ORM-view, а
`list` страницы показывают только компактный operational набор колонок без
лишнего горизонтального скролла. Для create-flow используется операторский UX
поверх application use cases:

- `tenants`: только `tenant_id` и `name`
- `assets`: `Tenant` selector + `asset_id`, `name`, `description`
- `agents`: `Asset` selector + `agent_id`, `name`
- `sources`: `Agent` selector + `source_id`, `source_type`, `enabled`, `name`,
  `description`
- `points`: `Source` selector + business-поля точки
- `agent_runtime_config_revisions`: `Agent` selector + revision payload
- `source_config_revisions`: `Source` selector + revision payload

Системные поля вроде `status`, `created_at`, `updated_at` и родительские ключи
для вложенных сущностей не вводятся руками на create-страницах.

Важно: прямое редактирование registry state через CRUD не создает новую
`config_revision` и не пишет `config_outbox` автоматически. После таких правок
оператор должен явно вызвать render action, иначе MQTT retained config не
изменится.

В backoffice этот render action живет прямо на `Agent` list/detail как
`Собрать config`. Action работает в agent scope: собирает
agent runtime/source config revision для выбранного агента и создает
`config_outbox` тем же application path, что и HTTP API.
Internal outbox actions `POST /backoffice/config-outbox/retry` и
`POST /backoffice/config-outbox/dead-letter` также вызывают application use
cases и не обновляют ORM-модели напрямую.

Для локальной доставки config records в Kafka используется
`KAFKA_BOOTSTRAP_SERVERS` и `CONFIG_REGISTRY_KAFKA_CLIENT_ID`.

Один batch pending outbox records можно отправить в Kafka командой:

```bash
uv run --package idp-config-registry idp-config-registry publish-config-outbox-once
```

Production-like local worker запускается отдельным процессом/контейнером:

```bash
uv run --package idp-config-registry idp-config-registry publish-config-outbox-worker
```

Worker опрашивает `config_outbox` с периодом
`CONFIG_REGISTRY_OUTBOX_POLL_INTERVAL_SECONDS` (`2.0` секунды по умолчанию),
публикует batch в Kafka и использует lease/retry/dead-letter настройки из
`CONFIG_REGISTRY_OUTBOX_*`.
