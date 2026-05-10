# ADR-006: Monorepo-структура для MVP и единый workspace для Python-пакетов

Дата: 2026-03-28  
Статус: accepted

## Контекст

Репозиторий уже содержит несколько независимых, но тесно связанных частей решения:

- `arch/` — LikeC4-модель и Node.js tooling для архитектуры
- `docs/architecture/` — верхнеуровневые архитектурные документы и ADR
- `apps/edge_telemetry_agent/` — основной runtime edge-агента на Python
- `apps/knx_demo/` — Python-утилиты и сценарии для demo-стенда
- `libs/knx_project_parser/` — Python-библиотека для разбора `ETS .knxproj`

Для текущего этапа проект остается `MVP`: архитектура, доменные контракты и
Python-код меняются согласованно, часто в одном pull request. Разделение на
несколько репозиториев сейчас создаст лишние накладные расходы:

- усложнит синхронное изменение архитектуры, контрактов и runtime-кода
- добавит избыточную публикацию внутренних пакетов и межрепозиторные версии
- усложнит локальную разработку и быстрые эксперименты по `KNX-first` сценарию

Одновременно уже видно, что репозиторий нужно сделать более явным monorepo, а
не просто набором соседних директорий.

Из внешних ориентиров важны следующие факты:

- `uv workspaces` предназначены для нескольких пакетов в одном репозитории и
  работают с единым lockfile для всех workspace members
- `uv` начинает поиск workspace-конфигурации от корня workspace и разделяет ее
  между всеми members
- `src` layout остается рекомендуемым вариантом для импортируемых пакетов и
  библиотек в Python

## Решение

### 1. Репозиторий остается единым monorepo на весь MVP

Для этапа `MVP` принимается один Git-репозиторий как основной способ
организации проекта.

- архитектура, ADR, демо-утилиты и edge runtime хранятся вместе
- отдельные репозитории не создаются до появления реальной организационной
  необходимости: независимых release cycles, другой команды владения или
  жесткой необходимости публиковать библиотеки отдельно

### 2. В репозитории вводится явная структура `apps / libs / tools / infra / environments / arch / docs`

Целевая верхнеуровневая структура:

```text
.
├── apps/
│   ├── edge_telemetry_agent/
│   └── knx_demo/
├── libs/
│   └── knx_project_parser/
├── tools/
│   └── idp_telemetry_store/
├── infra/
│   └── local/
├── environments/
│   └── demo-stand/
├── arch/
├── docs/
│   └── architecture/
├── scripts/
├── pyproject.toml
└── uv.lock
```

Правила интерпретации:

- `apps/` — deployable или operator-facing Python-приложения
- `libs/` — переиспользуемые Python-библиотеки без собственной operational роли
- `tools/` — repo-native tooling и operational CLI/automation packages; они могут
  быть оформлены как Python workspace packages, но их primary role — выполнять
  операции, migration flows или repo-level automation, а не поставлять доменную
  библиотеку для других модулей
- `infra/` — docker compose, локальные сервисы разработки и другие
  environment-level артефакты, общие для нескольких приложений
- `environments/` — versioned edge profiles конкретных стендов и окружений,
  если они не содержат секретов
- `arch/` — отдельный Node.js workspace для LikeC4, не смешиваемый с Python
- `docs/` — ADR, контракты, пояснения и текстовая архитектурная документация
- `scripts/` — repo-level automation, не являющаяся доменной библиотекой

Текущие Python-каталоги приведены к этой схеме:

- `apps/edge_telemetry_agent/`
- `apps/knx_demo/`
- `libs/knx_project_parser/`
- `libs/idp_demo_stack/`
- `tools/idp_telemetry_store/`

Критерий различия `libs/` и `tools/`:

- если пакет нужен другим частям кода как импортируемая библиотека, он живет в
  `libs/`
- если пакет в первую очередь является migration/runtime/ops CLI или repo tool,
  он живет в `tools/`

Из этого следует:

- `knx_project_parser` остается в `libs/`, потому что это самостоятельный Python API для
  чтения `ETS .knxproj`, а CLI является оберткой поверх библиотечной функции
- `idp_demo_stack` тоже остается в `libs/`, потому что его модели и генераторы
  импортируются из integration-тестов и локальных shim-скриптов, то есть он уже
  выступает как библиотека, а не только как команда публикации demo-событий
- `idp-telemetry-store` живет в `tools/`, потому что его primary role — migration и
  operational tooling для `Telemetry Store`

### 3. Для Python-части принимается единый `uv workspace`

Python-проекты внутри monorepo должны быть объединены одним корневым
`uv workspace`.

- в корне репозитория появляется `pyproject.toml` с `[tool.uv.workspace]`
- workspace members включают `apps/*`, `libs/*` и `tools/*`
- используется один корневой `uv.lock`
- команды `uv lock`, `uv sync` и общие developer workflows выполняются от корня
- при необходимости команды по конкретному пакету запускаются через
  `uv run --package <package-name> ...`

Корневой `pyproject.toml` рассматривается как workspace root, а не как отдельное
продуктовое приложение.

- корень не должен содержать доменный Python-код
- корень может хранить shared `tool.uv` настройки и общие dependency groups
- корень может оставаться непакетируемым workspace root без собственного
  distributable package

### 4. Границы пакетов сохраняются жесткими

Каждый Python-пакет сохраняет собственные:

- `pyproject.toml`
- `src/<package_name>/`
- `tests/`
- `README.md`

При этом не вводится абстрактный пакет вида `common`, `shared` или `utils`
заранее.

Правило извлечения общей библиотеки:

- код выносится в `libs/` только после появления второго реального consumer-а
- библиотека должна иметь предметное имя, отражающее bounded context, например
  `knx-contracts`, `telemetry-contracts`, `protocol-adapters`, а не безликий
  `shared`

### 5. `arch/` и LikeC4 остаются отдельным top-level контуром

Каталог `arch/` не включается в Python workspace.

- у `arch/` отдельный `package.json` и отдельный Node.js lifecycle
- LikeC4 остается source of truth для диаграмм и не смешивается с Python
  packaging
- технически это уменьшает связность toolchain
- организационно это сохраняет понятную границу: `arch/` отвечает за модель
  архитектуры, а `apps/`, `libs/` и `tools/` — за исполняемый Python-код и
  связанное workspace tooling

### 6. Локальная инфраструктура разработки хранится отдельно от `apps`

Для локального developer setup принимается отдельный каталог `infra/local/`.

В нем размещаются:

- `docker-compose.yml` или `compose.yaml` для shared developer services
- конфиги `MQTT broker`
- при необходимости дополнительные локальные сервисы вроде тестового БД,
  consumer-а, observability-компонентов или UI-debug surface

Принципы:

- `apps` не должны содержать внутри себя shared `docker compose` для всей
  локальной среды
- приложения подключаются к инфраструктуре через явные конфиги и environment
  variables, а не через жесткую привязку к путям репозитория
- локальная инфраструктура рассматривается как dev/test environment, а не как
  production deployment contract

Если `edge_telemetry_agent` и другие приложения запускаются на хосте через `uv`, а
инфраструктура поднимается в Docker, стандартной точкой подключения должны быть
`localhost`-адреса и порты, а не compose service names. Имена сервисов внутри
compose-сети используются только если сами приложения тоже запускаются в том же
compose-проекте.

На текущем этапе разработки обязательный локальный dev/test контур ограничен
`MQTT broker` и integration-тестами `KNX -> edge_telemetry_agent -> MQTT`.

Это решение фиксирует текущую границу MVP edge-telemetry-agent:

- smoke-test публикации событий из `edge_telemetry_agent` выполняется через MQTT tests
- проверка topic tree, payload contract и аутентификации выполняется без UI слоя
- Grafana остается целевым visualization layer платформы, но не входит в
  обязательный локальный demo surface edge-telemetry-agent
- production Grafana должна читать подготовленные данные из `Telemetry Store`,
  а не быть consumer-ом raw MQTT-потока

### 7. Конфигурационные файлы разделяются по ownership и назначению

Для monorepo принимаются три класса конфигурации.

#### 7.1. Product-owned templates и defaults

Такие файлы хранятся рядом с владельцем сервиса или приложения.

Примеры:

- `apps/edge_telemetry_agent/config/examples/bootstrap.example.yaml`
- `docs/contracts/edge-telemetry-agent/config-bundle.v1.md`
- `infra/local/mosquitto/mosquitto.conf`

Правила:

- это versioned файлы в Git
- они описывают формат, дефолты, примеры и dev-friendly presets
- они не должны содержать production secrets

#### 7.2. Environment-specific operations bundle

Конкретные operations bundles для стенда, объекта или dev-окружения хранятся
отдельно от исходников приложения в `environments/<environment-name>/`.

Пример структуры:

```text
environments/
└── demo-stand/
    ├── edge-config-bundle.yaml
    └── local.env
```

Правила:

- здесь лежат не “примеры”, а конкретные operations inputs
- каталог группируется по окружению или стенду, а не по технологии
- такие конфиги можно коммитить только если в них нет секретов и чувствительных
  endpoint-данных
- config delivery pipeline читает bundle или Platform Store, валидирует
  revision, пишет Kafka delivery record и материализует retained MQTT
  agent runtime/source configs через Redpanda Connect projection

Для `edge_telemetry_agent` это особенно важно: runtime boundary агента — retained MQTT
configs, а authoring boundary первого этапа — versioned YAML config bundle.

#### 7.3. Secrets и machine-local overrides

Секреты и машинно-специфичные override-файлы не хранятся в Git.

Примеры:

- `.env.local`
- `.secrets/`
- локальные credentials для `MQTT`, БД и внешних API

Правила:

- в репозитории допускаются только `.example`-файлы
- реальные секреты передаются через environment variables, Docker secrets,
  secret store или gitignored local files

Это разделение нужно, чтобы не смешивать:

- структуру формата конфигурации
- конкретную конфигурацию стенда
- секреты и локальные override-настройки

### 8. Текущая роль существующих модулей фиксируется так

- `apps/edge_telemetry_agent` — основной production-oriented runtime
- `apps/knx_demo` — demo и инженерные сценарии для стенда
- `libs/knx_project_parser` — самостоятельная библиотека, которую могут использовать
  и demo tooling, и будущие сервисы импорта/конфигурации
- `infra/local` — локальная среда разработки с `MQTT broker` и другими общими
  сервисами
- `environments/*` — конкретные edge profiles стендов, объектов и локальных
  профилей запуска

Наблюдение по текущему состоянию репозитория: прямых зависимостей между этими
пакетами пока почти нет. Это означает, что сейчас нужно вводить не “единый
суперпакет”, а единый workspace и понятные каталожные границы.

## Обоснование

- Один репозиторий лучше соответствует стадии `MVP`, где архитектура, runtime,
  demo tooling и документация меняются синхронно.
- Разделение `apps` и `libs` делает различие между deployable runtime и
  переиспользуемой библиотекой явным уже на уровне пути.
- Выделенный `infra/` не дает смешивать код приложений с локальной средой
  разработки и deployment-артефактами.
- Выделенный `environments/` не дает смешивать template-конфиги продукта с
  конфигами конкретного стенда или объекта.
- Единый `uv workspace` дает один lockfile и единый developer workflow без
  необходимости вручную синхронизировать несколько Python-окружений.
- `src` layout уже используется в текущих Python-пакетах и его стоит сохранить,
  потому что он снижает риск случайных импортов из корня репозитория.
- Отдельный `arch/` сохраняет мульти-toolchain monorepo управляемым: Python и
  Node.js tooling живут рядом, но не маскируются под один и тот же workspace.
- Отказ от преждевременного `shared/` уменьшает риск возникновения “мусорной”
  общей библиотеки с размытыми зависимостями.

## Последствия

Положительные:

- репозиторий становится явно организованным как monorepo, а не набором
  соседних проектов
- у Python-части появляется единая точка входа для lock/sync/run
- локальная инфраструктура получает собственное предсказуемое место в
  репозитории
- конкретные edge profiles стендов получают отдельное предсказуемое место и
  не засоряют каталоги приложений
- архитектурные артефакты и код остаются рядом, что удобно для быстрых
  итераций в `MVP`
- будущие зависимости между пакетами можно оформлять через workspace dependency,
  а не через локальные path-хаки
- упрощается onboarding: сразу видно, где приложение, где библиотека и где
  архитектурная модель

Отрицательные:

- понадобится миграция путей и локальных команд после переноса каталогов в
  `apps/` и `libs/`
- единый workspace означает единый lockfile и общую дисциплину по версиям
  Python-зависимостей
- CI придется перестроить на root-level сценарии и package-scoped команды
- понадобится дисциплина по тому, какие environment-конфиги можно хранить в
  Git, а какие нужно оставлять только локально или в secret store

## Отклоненные альтернативы

- Сразу разнести `edge_telemetry_agent`, `knx_demo` и `knx_project_parser` по отдельным
  репозиториям: преждевременно для `MVP`, увеличивает накладные расходы на
  синхронизацию контрактов и локальную разработку.
- Оставить все Python-проекты плоско в корне репозитория: работает только пока
  каталогов мало, но быстро теряет семантику и затрудняет навигацию.
- Хранить реальные runtime-конфиги внутри каталогов приложений рядом с
  example-файлами: со временем смешивает шаблоны продукта, конфиги стендов и
  секреты.
- Хранить shared developer `docker compose` внутри одного из `apps`: приводит к
  скрытому владению общей инфраструктурой одним приложением, хотя ею пользуются
  несколько частей репозитория.
- Свести все в один Python-пакет: разрушает границы между runtime, demo tooling
  и библиотекой парсинга.
- Включить `arch/` как member Python workspace: не соответствует отдельному
  Node.js toolchain и ломает ясность границ.
- Создать общий пакет `shared/common` заранее: слишком рано и почти наверняка
  приведет к сваливанию разнотипного кода в один “технический” модуль.

## Реализация

1. Создан корневой `pyproject.toml` для `uv workspace`.
2. `edge_telemetry_agent` и `knx_demo` перенесены в `apps/`.
3. `knx_project_parser` перенесен в `libs/`.
4. `README.md`, package README и архитектурные документы переведены на новые пути.
5. Следующим шагом остается развивать `infra/local/` и environment-specific edge profiles.

## Внешние ориентиры

- `uv workspaces`: [Using workspaces](https://docs.astral.sh/uv/concepts/projects/workspaces/)
- `uv shared configuration`: [Configuration files](https://docs.astral.sh/uv/concepts/configuration-files/)
- `uv packaging behavior`: [Configuring projects](https://docs.astral.sh/uv/concepts/projects/config/)
- `PyPA src layout guidance`: [src layout vs flat layout](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/)
