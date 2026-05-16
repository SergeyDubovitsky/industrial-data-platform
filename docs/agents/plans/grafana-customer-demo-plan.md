# План: клиентское демо в Grafana

**Сформировано**: 2026-05-11
**Оценочная сложность**: средняя

## Обзор

Цель: подготовить локальное демо для заказчика, которое показывает, что
платформа работает end-to-end в реальном времени:

```text
Synthetic Moscow mall KNX source
  -> Edge Telemetry Agent
  -> MQTT idp/v1/...
  -> Redpanda Connect
  -> Kafka idp.*
  -> Kafka Connect
  -> ClickHouse Telemetry Store
  -> Grafana dashboard
```

Демо должно работать непрерывно до ручной остановки, показывать живую телеметрию
в Grafana без фиксированного лимита событий и использовать правдоподобные данные
для большого торгового центра в центре Москвы.

## Допущения

- Первая цель — презентация заказчику, а не production frontend для Web
  Monitoring.
- Grafana остается текущей поверхностью Web Monitoring Module и читает только
  ClickHouse read models.
- Синтетический эмулятор должен запускаться с `--forever`; Edge Telemetry Agent
  должен запускаться без `--max-events`.
- Демо использует вымышленный, но реалистичный большой торговый центр в центре
  Москвы.
- Масштаб presentation-профиля по умолчанию — `100` синтетических устройств.
- Заголовки dashboard, подписи панелей и customer-facing runbook пишутся на
  русском языке.
- Старые Grafana dashboards не остаются в demo surface: новый customer-facing
  dashboard должен заменить существующий engineering dashboard.
- Существующие контракты остаются стабильными. Любая новая ClickHouse view или
  публичная storage-поверхность должна обновлять
  `docs/contracts/clickhouse/telemetry-store.v1.md`.

## Текущая база в репозитории

- Локальный запуск платформы уже есть в `infra/local/up-platform.sh`.
- Ручной сценарий запуска эмулятора уже есть в `infra/local/emulator-runbook.md`.
- Синтетический конфиг ТЦ генерируется через `libs/idp_synthetic_config`.
- TCP KNX-like source emulator уже есть в `apps/knx_source_emulator`.
- Synthetic bootstrap для Edge agent уже есть в
  `apps/edge_telemetry_agent/config/examples/bootstrap.synthetic-emulator.yaml`.
- Grafana provisioning уже лежит в `infra/local/grafana`.
- Существующий dashboard, который нужно заменить или удалить в рамках демо:
  `infra/local/grafana/dashboards/telemetry-overview.json`.
- Существующая integration-поверхность:
  `tests/integration/test_grafana_clickhouse.py`.

## Использованные ориентиры

- Grafana provisioning поддерживает file providers с `updateIntervalSeconds`,
  размещением в папке, `allowUiUpdates` и загрузкой dashboard JSON с диска.
- Grafana ClickHouse datasource можно provision через YAML с использованием
  `grafana-clickhouse-datasource`.
- ClickHouse/Grafana time series queries должны возвращать datetime-колонку с
  alias `time` и числовую колонку значения.
- Согласно `schema-pk-filter-on-orderby`, dashboard queries по возможности
  должны фильтровать по префиксу ClickHouse sort key:
  `tenant_id`, `asset_id`, `source_id`, `point_key`, `ts`.
- Согласно `query-mv-incremental`, dashboard должен предпочитать существующие
  read models и rollups для агрегатов, а не тяжелую ad hoc агрегацию по raw data.
- Согласно `agent-query-safety`, exploratory/demo queries должны иметь
  ограниченный time range, row limits и избегать неограниченного `SELECT *`.

## Scope

- Отполированный русскоязычный customer demo dashboard для live telemetry.
- Повторяемая локальная команда или runbook для непрерывной работы демо.
- Synthetic data profile для вымышленного большого торгового центра в центре
  Москвы, с `100` устройствами по умолчанию в presentation mode.
- Автоматическая проверка, что dashboard provisioned и может читать живые или
  близкие к живым данные из ClickHouse.

## Out Of Scope

- Tenant-facing Web Monitoring frontend.
- Полный asset framework.
- Alarm Management runtime.
- Production cloud deployment.
- Production auth/IAM.
- Замена Grafana на другой UI.

## Deliverables

- Единственный provisioned Grafana dashboard для demo surface, вероятно:
  `infra/local/grafana/dashboards/customer-demo-moscow-mall.json`.
- Удаленный или замененный старый dashboard
  `infra/local/grafana/dashboards/telemetry-overview.json`.
- Обновленный или новый demo runbook в `infra/local/`.
- Опциональный demo runner script в `infra/local/scripts/`.
- Улучшения synthetic config/emulator в `libs/idp_synthetic_config/` и
  `apps/knx_source_emulator/`, если текущий generator не сможет чисто выразить
  demo-story.
- Integration tests для Grafana dashboard provisioning и ClickHouse query
  behavior.

## Спринт 1: непрерывный real-time demo path

**Цель**: заставить текущий локальный stack работать бесконечно с синтетической
телеметрией ТЦ и подтвердить, что данные доходят до ClickHouse.

**Демо/валидация**:

- Запустить local stack.
- Запустить emulator с `--forever`.
- Запустить edge agent без `--max-events`.
- Проверить свежие строки в `telemetry_events_v1` и `telemetry_latest_v1`.

### Issue 1: зафиксировать критерии успеха демо и operator script

- **Labels**: `demo`, `web-monitoring`, `infra-local`
- **Location**:
  - `infra/local/emulator-runbook.md`
  - опционально `infra/local/customer-demo-runbook.md`
- **Description**: описать точные acceptance criteria для customer demo и
  ручную последовательность start/stop.
- **Dependencies**: нет
- **Acceptance Criteria**:
  - Документ описывает полную последовательность команд от чистого локального
    окружения до Grafana.
  - Явно используется emulator `--forever`.
  - Edge agent явно запускается без `--max-events`.
  - Определено, что значит "demo is working": новые MQTT events, Kafka records,
    ClickHouse rows, обновляющиеся панели Grafana.
  - Есть reset/cleanup и troubleshooting для пустой Grafana.
- **Validation**:
  - `git diff --check`
  - Ручная сверка команд с существующим `infra/local/emulator-runbook.md`.

### Issue 2: добавить continuous demo runner одной командой

- **Labels**: `demo`, `developer-experience`, `infra-local`
- **Location**:
  - `infra/local/scripts/`
  - `infra/local/README.md`
  - `infra/local/emulator-runbook.md`
- **Description**: добавить локальный helper, который запускает или
  supervises непрерывные demo processes после старта platform stack:
  ClickHouse migrations, Kafka Connect bootstrap, synthetic emulator и edge
  source adapter.
- **Dependencies**: Issue 1
- **Acceptance Criteria**:
  - Helper не скрывает ошибки и печатает точный failed step.
  - Использует существующие package CLIs, а не дублирует business logic.
  - Пишет logs в `.local/`.
  - Поддерживает bounded smoke mode для тестов и unbounded presentation mode для
    customer demo.
  - Не делает destructive reset, если это явно не запрошено.
- **Validation**:
  - Bounded smoke mode успешно проходит.
  - Существующие tests для затронутых package CLIs продолжают проходить.

## Спринт 2: synthetic story московского ТЦ

**Цель**: сделать live data похожими на реалистичный большой торговый центр в
центре Москвы, а не на generic technical smoke test.

**Демо/валидация**:

- Generated config содержит узнаваемые зоны, этажи, системы и signal types.
- Grafana может показывать значения по engineering subsystem и zone.

### Issue 3: добавить customer demo synthetic profile

- **Labels**: `demo-data`, `synthetic-config`
- **Location**:
  - `libs/idp_synthetic_config/src/idp_synthetic_config/generator.py`
  - `libs/idp_synthetic_config/tests/test_generator.py`
  - `libs/idp_synthetic_config/README.md`
- **Description**: добавить или настроить deterministic profile для большого
  торгового центра в центре Москвы.
- **Dependencies**: нет
- **Acceptance Criteria**:
  - Asset name и descriptions готовы для презентации на русском языке.
  - Asset naming вымышленный и не должен создавать впечатление реального
    customer object.
  - Generated devices покрывают HVAC, освещение, эскалаторы, лифты, насосы,
    энергомониторинг, парковку, качество воздуха, пожарные/security statuses.
  - Tags включают `floor`, `zone`, `subsystem`, `tenant_space`, `device_id`,
    `signal_type` и `value_model`.
  - Presentation profile по умолчанию использует `100` устройств.
  - Для быстрой локальной проверки остается меньший smoke/test profile.
  - Верхние local-load bounds остаются enforced.
- **Validation**:
  - `uv run --package idp-synthetic-config pytest libs/idp_synthetic_config/tests`
  - `uv run --package idp-synthetic-config idp-synthetic-config plan --format json`

### Issue 4: настроить live cadence эмулятора для презентации

- **Labels**: `demo-data`, `emulator`
- **Location**:
  - `apps/knx_source_emulator/src/knx_source_emulator/`
  - `apps/knx_source_emulator/tests/`
  - `apps/knx_source_emulator/README.md`
- **Description**: убедиться, что emulator может генерировать плавные live
  changes для Grafana без перегруза локальных ClickHouse/Kafka.
- **Dependencies**: Issue 3
- **Acceptance Criteria**:
  - Presentation mode может emit с визуально заметным интервалом, например
    `1` секунда.
  - Values меняются правдоподобно для температуры, CO2, энергопотребления,
    влажности, положения приводов и statuses.
  - Command points по-прежнему не публикуются как telemetry.
  - Emulator может работать forever до ручной остановки.
- **Validation**:
  - `uv run --package knx-source-emulator pytest apps/knx_source_emulator/tests`
  - Bounded local run с `--duration-seconds` проверяет event counts.

## Спринт 3: customer-facing Grafana dashboard

**Цель**: создать dashboard, который рассказывает понятную customer-facing
story: торговый центр online, телеметрия идет, live trends видны.

**Демо/валидация**:

- Открыть Grafana и выбрать `Web Monitoring / Customer Demo - Moscow Mall`.
- Панели автоматически обновляются во время работы emulator/edge process.

### Issue 5: заменить старый Grafana dashboard customer demo dashboard

- **Labels**: `grafana`, `web-monitoring`, `demo`
- **Location**:
  - `infra/local/grafana/dashboards/customer-demo-moscow-mall.json`
  - `infra/local/grafana/dashboards/telemetry-overview.json`
  - возможно `infra/local/grafana/provisioning/dashboards/dashboards.yaml`
- **Description**: заменить существующий engineering dashboard `Telemetry
  Overview` единственным customer-facing dashboard для презентации.
- **Dependencies**: Issues 3 and 4
- **Acceptance Criteria**:
  - Dashboard provisioned в папке `Web Monitoring`.
  - В Grafana demo surface остается один dashboard для customer demo.
  - Старый `Telemetry Overview` не отображается рядом с customer demo.
  - Если используется новый JSON filename, старый `telemetry-overview.json`
    удален или исключен из provisioning.
  - Dashboard title и customer-facing panel text на русском языке.
  - Refresh достаточно быстрый для демо, например `5s` или `10s`.
  - Time range по умолчанию — live window, например `now-15m` to `now`.
  - Включены панели:
    - система online / возраст последнего события;
    - события в минуту;
    - активные точки;
    - live trends для температуры, CO2, энергии и положения приводов;
    - таблица последних значений;
    - распределение quality/status;
    - секция ingestion diagnostics.
  - Queries фильтруются по известным demo `tenant_id`, `asset_id` и
    `source_id`.
  - Query outputs ограничены time filters и limits.
- **Validation**:
  - Dashboard загружается через Grafana API.
  - Grafana datasource query возвращает хотя бы одно свежее значение после
    bounded demo run.
  - Существующий `tests/integration/test_grafana_clickhouse.py` продолжает
    проходить.

### Issue 6: добавить dashboard variables и человекочитаемые labels

- **Labels**: `grafana`, `ux`, `clickhouse`
- **Location**:
  - `infra/local/grafana/dashboards/customer-demo-moscow-mall.json`
  - опционально ClickHouse contract/migration files, если выбрана новая read
    view
- **Description**: добавить полезные dashboard filters и labels без введения
  полного asset framework.
- **Dependencies**: Issue 5
- **Acceptance Criteria**:
  - Dashboard имеет variables для tenant/asset/source или fixed hidden constants
    для demo.
  - Operator-visible labels используют point metadata там, где это практично:
    zone, subsystem, point name, unit.
  - Если metadata извлекается из `source_config_snapshots_v1`, queries scoped
    по demo tenant/asset/source и latest config revision.
  - Если добавляется новая ClickHouse view, обновлен ClickHouse contract doc.
- **Validation**:
  - Grafana API query для variables проходит.
  - ClickHouse query plan остается ограниченным tenant/asset/source/time
    filters.

## Спринт 4: проверка и репетиция

**Цель**: сделать демо достаточно повторяемым, чтобы его можно было спокойно
запускать под давлением презентации.

**Демо/валидация**:

- Одна задокументированная репетиция с чистого local state.
- Один задокументированный recovery path для каждой частой ошибки.

### Issue 7: добавить end-to-end demo smoke test

- **Labels**: `integration`, `grafana`, `demo`
- **Location**:
  - `tests/integration/`
  - возможно shared fixtures в `tests/integration/conftest.py`
- **Description**: добавить bounded integration test, который доказывает, что
  demo dashboard может querying data после короткого synthetic run.
- **Dependencies**: Issues 2 and 5
- **Acceptance Criteria**:
  - Test не работает forever.
  - Test seeds synthetic config, emits небольшой bounded stream, runs edge
    adapter, waits for ClickHouse и queries Grafana API.
  - Test asserts, что customer demo dashboard существует и возвращает recent
    data.
- **Validation**:
  - `uv run --group integration pytest tests/integration/test_grafana_clickhouse.py`
  - Новая targeted integration test command задокументирована в issue.

### Issue 8: финальный checklist для репетиции демо

- **Labels**: `demo`, `release-readiness`
- **Location**:
  - `infra/local/customer-demo-runbook.md`
  - `README.md` или `infra/local/README.md`
- **Description**: создать финальный presentation checklist.
- **Dependencies**: Issues 1-7
- **Acceptance Criteria**:
  - Включает preflight checks для Docker, `.env`, ports и stale volumes.
  - Включает ordered tabs для открытия: Grafana, Kafka UI, MQTTX, Config
    Registry.
  - Включает story для рассказа: source emulator -> edge -> MQTT -> Kafka ->
    ClickHouse -> Grafana.
  - Включает emergency fallback: load PoC data, если live pipeline unavailable.
  - Включает screenshots или expected panel names, если это полезно.
- **Validation**:
  - Full rehearsal from clean local stack.
  - `git diff --check`.

## Рекомендуемый порядок issues

1. Issue 1: зафиксировать критерии успеха демо и runbook.
2. Issue 2: добавить continuous demo runner одной командой.
3. Issue 3: добавить customer demo synthetic profile.
4. Issue 4: настроить live cadence эмулятора.
5. Issue 5: добавить customer demo dashboard JSON.
6. Issue 6: добавить dashboard variables и человекочитаемые labels.
7. Issue 7: добавить end-to-end demo smoke test.
8. Issue 8: финальный checklist для репетиции демо.

Issues 3 и 5 можно начинать параллельно после Issue 1. Issue 7 лучше начинать
после стабилизации demo runner и формы dashboard.

## Стратегия тестирования

- Package tests:
  - `uv run --package idp-synthetic-config pytest libs/idp_synthetic_config/tests`
  - `uv run --package knx-source-emulator pytest apps/knx_source_emulator/tests`
  - `uv run --package edge-telemetry-agent pytest apps/edge_telemetry_agent/tests`
- Local infra validation:
  - `docker compose -f infra/local/compose.yaml config --quiet`
- Grafana/ClickHouse integration:
  - `uv run --group integration pytest tests/integration/test_grafana_clickhouse.py`
- Full data path rehearsal:
  - `./infra/local/up-platform.sh`
  - `uv run --env-file .env idp-telemetry-store migrate up`
  - `uv run --env-file .env python infra/local/kafka-connect/bootstrap_connector.py`
  - запустить emulator forever
  - запустить edge agent без `--max-events`
  - проверить, что панели Grafana обновляются

## Риски и подводные камни

- Grafana может выглядеть пустой, если time range слишком широкий, слишком
  узкий или dashboard читает 1-minute rollups, когда данных накопилось только
  на несколько секунд.
- Существующая `telemetry_events_dedup_v1` использует `FINAL`; это приемлемо для
  local demo scale, но не должно становиться default production dashboard query
  pattern без load validation.
- Очень большие synthetic profiles могут перегрузить локальные Kafka Connect
  или ClickHouse во время laptop demo.
- Metadata-rich labels могут потребовать parsing `source_config_snapshots_v1`;
  это нормально для demo scale, но queries должны оставаться bounded и
  documented.
- Stale retained MQTT volume может запутать демо; runbook должен включать reset
  check для старых `wm/#` topics.
- Customer-facing naming не должен создавать впечатление интеграции с реальным
  московским ТЦ.

## План отката

- Для отката можно восстановить прежний `telemetry-overview.json` из git и
  restart/reload Grafana provisioning.
- Изменения synthetic profile должны сохранять backward-compatible defaults или
  быть включены через явные CLI flags/profile options.
- Demo runner должен быть additive и не должен заменять существующие ручные
  команды.

## Проверка ADR / LikeC4

- ADR скорее всего не нужен, если это остается local demo tooling и Grafana
  dashboard work внутри существующей границы Web Monitoring Module.
- LikeC4 скорее всего не нужен, если план не вводит новый runtime component или
  durable deployment path.
- Contract docs нужны только если добавляется новая ClickHouse read model/view
  или публичная storage surface.

## Решенные вопросы

Решено 2026-05-11:

- Использовать вымышленный московский торговый центр.
- Использовать `100` устройств для default presentation profile.
- Customer-facing dashboard и runbook писать только на русском языке.
