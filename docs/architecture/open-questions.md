# Открытые вопросы и развилки

Дата: 2026-05-10
Статус: open

Документ актуализирован после сверки:

- верхнеуровневой markdown-документации в `docs/architecture/`
- LikeC4-модели в `arch/likec4/`
- текущей Python-реализации в `apps/edge_telemetry_agent/` и `apps/knx_demo/`
- локального dev-контура в `infra/local/`
- versioned edge profile demo-стенда в `environments/demo-stand/`

## Что уже зафиксировано в репозитории

- Для `demo-stand` уже есть versioned edge profile первого `KNX`-среза:
  `0/0/1` как `command`, `0/0/7` как `feedback`, `2/0/0` как `sensor`.
- В текущем конфиге `read_on_start` уже включен для `0/0/7` и `2/0/0`, а
  `change_threshold = 1.0` уже задан для температуры.
- В коде `edge_telemetry_agent` уже реализованы и покрыты тестами:
  загрузка bootstrap + retained agent runtime/source config, fail-fast валидация,
  подавление `command`-точек, threshold-based processing и `SQLite Delivery Outbox`.
- В коде и `infra/local/` уже зафиксирован рабочий локальный dev-контур:
  `MQTT broker`, `Apache Kafka`, `Redpanda Connect` ingestion/config projection
  pipelines, `PostgreSQL`, `Config Registry`, `ClickHouse`, `Kafka Connect` и
  `Grafana`.
- Для целевой configuration-модели принято: edge-telemetry-agent получает
  retained agent runtime/source configs из MQTT; delivery path идет как
  PostgreSQL config outbox -> Kafka -> MQTT retained projection.
- Для локального config delivery baseline уже реализованы `Config Registry`
  outbox publisher и Redpanda Connect projection
  `idp.edge.configs.v1 -> retained MQTT agent runtime/source topics`.
- Для локального storage/read baseline уже реализованы `ClickHouse`
  migrations, `Kafka Connect` raw landing path и `Grafana` read-model
  проверка integration-тестом.
- Текущий проект уже достиг `MVP baseline`: `KNX/edge_telemetry_agent -> MQTT -> Kafka`
  ingestion slice работает в репозитории и покрыт integration-тестами.
- Post-MVP product/pilot direction: первый пилот cloud-first в российском
  облаке (`VK Cloud` или `Yandex Cloud`), local Docker infra остается
  обязательной для разработки и тестов, следующий protocol track —
  `OPC UA read-only ingestion`, а internal issue tracker используется как
  internal-only execution backlog.
- Полная `Industrial Data Platform` как `MQTT Ingestion Gateway`,
  `Redpanda Connect`, `Kafka-compatible Broker Runtime`, `Kafka Event Log`,
  storage writer/Kafka Connect, `Streaming Analytics`, `Telemetry Store`,
  `Platform Store`, `Config Registry` и shared IAM остается следующей фазой
  развития поверх текущего `MVP`.
- `Web Monitoring Module` и `Alarm Management Module` развиваются как отдельные
  модули поверх data platform; прежнее имя центральной системы больше не
  используется.

## Что принято в рабочих материалах по пилоту `KNX -> OPC`

- Для пилота `KNX -> OPC` принят отдельный сервисный контур: write-path
  допускается только из внешнего `OPC`-клиента, а не из web-monitoring UI/API.
- Для того же пилота принят контейнерный сценарий поставки на
  `Ubuntu Server LTS`; нативная дистрибуция на `Windows` выведена в отдельный
  проект и не считается частью текущего объема работ.

Ниже перечислены только те вопросы, которые остаются реально открытыми после
этой сверки.

## Исходные данные объекта и KNX-карта

| Вопрос | Почему это важно | Степень блокировки |
| --- | --- | --- |
| Являются ли текущие артефакты demo-стенда: `.local/Выстовка.knxproj*` и текущие YAML-файлы утвержденным source of truth для формирования первого `idp.edge.source-config.v1` bundle? | Agent runtime source of truth для edge-telemetry-agent должен приходить через retained MQTT configs, но исходная KNX-карта все равно нужна для генерации source config | Критично |
| Подтверждены ли для первого среза `read_on_start` и семантика чтения именно для `0/0/7` и `2/0/0`? | Versioned конфиг уже включает `read_on_start`, но это нужно подтвердить эксплуатационно, чтобы не зависеть от неподдерживаемого `GroupValueRead` | Высокая |
| Какой следующий утвержденный whitelist точек нужен после текущих `0/0/7` и `2/0/0`? | Без этого нельзя планировать второй инкремент адаптера, расширение point registry и проверку `value_model` beyond demo | Средняя |

## Целевая топология edge-узла

| Вопрос | Почему это важно | Степень блокировки |
| --- | --- | --- |
| Готов ли заказчик предоставить `Ubuntu Server LTS` host/VM для пилота `KNX -> OPC`, если текущая эксплуатационная среда у него `Windows Server 2019`? | Для пилота уже принят контейнерный сценарий эксплуатации на `Ubuntu`. Без подтверждения хоста или VM нельзя финализировать deployment, сетевые правила и операционный контур | Критично |
| Требуется ли после пилота отдельная эксплуатационная поставка на `Windows Server 2019`, или для заказчика достаточно контейнерной поставки на `Ubuntu Server LTS`? | Это влияет на roadmap, бюджет и границы следующего проекта. Сейчас `Windows`-дистрибуция явно вынесена за рамки текущего объема работ | Высокая |
| На каком классе хоста будет работать production `Edge Telemetry Agent`: industrial PC, VM, отдельный Linux-host или встроенный контроллер? | Сейчас рабочий dev-сценарий идет с `Developer Workstation`, а target topology требует отдельный edge-узел на объекте. Это влияет на packaging, watchdog, volume paths и lifecycle | Критично |
| Остается ли внешний NAT-доступ к `KNX/IP` строго dev-only сценарием, или нужен утвержденный remote maintenance path и для эксплуатации? | Сейчас документы разводят production topology и demo remote access. Нужно подтвердить сетевую политику, чтобы не спроектировать лишний или небезопасный ingress path | Высокая |
| Какой launcher берем для production edge runtime после cloud validation: `docker compose`, `systemd`-wrapper/OS service management или managed runtime? | Local Docker infra уже принят как dev/test baseline, а первый pilot target для `Industrial Data Platform` cloud-first; production edge lifecycle все еще требует отдельного решения | Средняя |
| Какой допустимый простой edge runtime при рестарте, обновлении и reconnect? | Это влияет на backoff policy, drain outbox, health semantics и требования к rolling update | Средняя |

## Следующий срез Industrial Data Platform и модулей

`Hierarchical Catalog V1` вынесен в отдельный working plan:
`docs/architecture/hierarchical-catalog-v1.md`. Runtime placement намеренно
оставлен открытым и вынесен в proposed
`docs/architecture/adrs/ADR-015-hierarchical-catalog-runtime-boundary.md`:
embedded slice внутри `Config Registry`, отдельный Catalog service/package или
shared library как вспомогательная техника после выбора runtime owner. Это еще
не accepted decision и не запись в `decisions.md`.

Важно не смешивать два use case: `Hierarchical Catalog V1` как
navigation/authoring tree и future `Digital Twin Registry` / `Asset Graph
Registry` как объектную модель реального мира с arbitrary attributes,
non-tree relations и telemetry bindings. Если первый implementation target
включает связь `source.point` / `point_code` / telemetry series ->
`twin.attribute`, unit, quality/status semantics или computed attributes, это
уже не простой Catalog V1.

Кандидат для ближайшего совместного обсуждения Industrial Data Platform / Web Monitoring:
решить, должен ли первый срез после `Config Registry` быть read-only
`latest/history` telemetry API поверх уже существующих ClickHouse read models
`telemetry_latest_v1` и `telemetry_events_dedup_v1`. Материал к обсуждению для
встречи: `docs/architecture/read-only-telemetry-api-discussion.md`.

Если команда выбирает этот путь, следующее архитектурное решение должно
зафиксировать отдельную tenant-facing read API boundary для `Web Monitoring
Module`, а не расширять `Config Registry` до telemetry/alarm API. Возможный
local/dev API surface для обсуждения:

- `GET /health`
- `GET /ready`
- `GET /v1/tenants/{tenant_code}/telemetry/latest`
- `GET /v1/tenants/{tenant_code}/telemetry/history`

До отдельного auth/RBAC решения `tenant_code` в этом candidate API surface
является явным local/dev input, а не результатом аутентифицированного контекста.
API/backoffice/domain используют `*_code`; `tenant_id` остается wire/storage
identity для Edge/Kafka/MQTT/ClickHouse.

Alarm workflow обсуждается рядом, но остается отдельным slice и будущим
решением `Alarm Management Module`: минимальный lifecycle (`active/raised`,
`acknowledged`, `cleared/resolved`, `severity`) уже обозначен в рабочих
материалах, но rule types, PostgreSQL current state, writer в
`alarm_history_events_v1`, operator workflow и notification policy еще не
зафиксированы. Operator UI, config rollout, auth/RBAC и write-back/control
также остаются отдельными открытыми вопросами.

| Вопрос | Почему это важно | Степень блокировки |
| --- | --- | --- |
| Первый implementation target — `Hierarchical Catalog V1` как navigation tree или `Digital Twin Registry` / `Asset Graph Registry` как объектная модель? | Эти use case требуют разной модели: дерево `folder`/`*_ref` достаточно для навигации, но twin-layer требует arbitrary attributes, telemetry bindings, unit/quality semantics и non-tree relations | Критично |
| Какой runtime owner выбираем после выбора scope: embedded slice внутри `Config Registry` или отдельный Catalog/Twin service/package? | Отдельный сервис технически реалистичен уже сейчас; решение должно опираться на ownership, source of truth, consistency, consumers и future Web Monitoring/Alarms dependency | Высокая |
| Нужны ли telemetry bindings в первом slice: `source.point` / `point_code` / telemetry series -> `twin.attribute`? | Без binding слой останется UI-деревом над registry rows; с binding он становится частью semantic enrichment и влияет на read API, alarm rules, unit/quality/status semantics и storage/API model | Высокая |
| Какие non-tree relation types нужны target graph: `partOf`, `locatedIn`, `connectedTo`, `feeds`, `poweredBy`, `measures`, `controls`? | Adjacency tree подходит для V1 projection, но цифровой двойник почти наверняка потребует graph semantics и несколько представлений | Средняя |
| Нужно ли мапиться на Brick/Haystack/RealEstateCore для smart-building domain или оставить собственную минимальную vocabulary до пилота? | Готовые building ontologies уже различают assets, points, sensors/commands/setpoints и relations; слепая собственная модель может осложнить интеграции | Средняя |
| Какие источники первыми создают catalog nodes: ручной `/backoffice`, synthetic generator, ETS/KNX import или будущий OPC UA importer? | V1 может хранить дерево независимо от importer-а, но acceptance сценарий должен выбрать первый workflow наполнения | Средняя |
| Какие конкретные API/use cases входят в первый tenant-facing API после `Config Registry`: telemetry read, config rollout, Web Monitoring read API или Alarm Management workflow API? | Data platform, Web Monitoring и Alarm Management разделены, поэтому следующий API contract должен явно назвать ownership | Высокая |
| Где фиксируется `Redpanda Connect` pipeline config: в platform repository, IaC, Redpanda Cloud-managed pipeline или отдельном operations bundle? | MQTT input, mapping/transform и redpanda output становятся частью production data path, поэтому конфигурация pipeline должна быть версионирована и управляться так же строго, как edge source config | Высокая |
| Нужно ли переходить с локального `Apache Kafka` broker runtime на `Redpanda broker`? | Apache Kafka остается локальным baseline; Redpanda broker требует отдельный compatibility PoC, чтобы не смешивать broker migration с connector/runtime cleanup | Средняя |
| Нужно ли менять draft Kafka topics, retention и consumer groups после нагрузочного PoC? | Базовый контракт зафиксирован в `docs/contracts/kafka/topics.v1.md`, но реальные partition counts и retention могут потребовать корректировки после измерений | Средняя |
| Какие изменения потребуются в draft ClickHouse DDL, rollups и TTL после обязательного нагрузочного PoC? | Load PoC является gate перед production schema; сами sizing/rollup/retention параметры должны быть подтверждены на данных целевого масштаба | Средняя |
| Какие alarm rule types и screens нужны поверх принятого минимального lifecycle `active/raised`, `acknowledged`, `cleared/resolved`, `severity`? | Минимальный lifecycle принят, но сами правила, thresholds, UI workflow и notification policy остаются продуктовой развилкой | Высокая |
| Какие notification channels требуются в первом production-срезе: email, Telegram, SMS, webhook или только in-app/Grafana? | `Notification Service` теперь относится к `Alarm Management Module`; без выбора каналов нельзя стабилизировать scope backend и интеграций | Средняя |
| Когда принимать отдельное решение по Keycloak/auth/JWT/users/roles? | Аутентификация специально исключена из config backend slice, чтобы не смешивать хранение настроек и IAM | Средняя |

## Cloud-first pilot и operations

| Вопрос | Почему это важно | Степень блокировки |
| --- | --- | --- |
| Что выбираем для первого cloud pilot: `VK Cloud` или `Yandex Cloud`? | Российский cloud-first pilot уже принят, но конкретный provider влияет на networking, managed PostgreSQL/ClickHouse/Kafka options, secrets, observability и стоимость | Критично |
| Какие managed services допустимы в cloud pilot, а какие компоненты держим как self-managed containers для parity с future self-hosted? | Provider optimization не должна менять contracts, migrations и acceptance tests, но может снизить операционную нагрузку первого пилота | Высокая |
| Как customer feedback из пилота попадает в internal issue tracker: вручную через triage или через отдельный customer-facing project/helpdesk/view? | Внешний доступ к internal backlog запрещен, но feedback loop нужно сделать удобным и безопасным | Средняя |

## MQTT delivery и безопасность

| Вопрос | Почему это важно | Степень блокировки |
| --- | --- | --- |
| Какой именно `MQTT broker` и endpoint используются в production, и кто ими владеет? | Локальный broker уже есть для dev и smoke-tests, но production transport пока не закреплен организационно и технически | Критично |
| Какие требования к `TLS`, client auth, certificates и topic ACL у production MQTT-брокера? | Это влияет на структуру secrets, bootstrap агента и publish/subscribe contract между edge и platform | Высокая |
| Где будут храниться production secrets: `.env`, file secret, `systemd` credentials, vault, Kubernetes secret store или иной способ? | Сейчас в репозитории уже есть env-placeholder модель, но production secret handling не зафиксирован | Высокая |
| Для первого production-объекта используется обычный `KNXnet/IP` или требуется `KNX Secure`? | Это прямо влияет на стек библиотек, ключевой материал и реальную применимость текущего `KNX-first` кода/инструментов | Высокая |

## Server-issued edge config

| Вопрос | Почему это важно | Степень блокировки |
| --- | --- | --- |
| Какой максимальный размер одного retained `idp.edge.source-config.v1` допустим для production MQTT broker? | Agent runtime config делится по `source_id`, но один source все равно может содержать десятки тысяч points. Нужно понять, когда потребуется chunking | Высокая |
| Как формировать deterministic `config_revision` и `source_config_revision`: human version, content hash или оба поля? | AI-agent должен давать воспроизводимый diff и publish summary, а edge/ingestion должны однозначно валидировать примененную версию | Высокая |
| Как Redpanda Connect projection должен публиковать rollback или отключение source: новый retained payload с `enabled=false` или retained tombstone? | Это влияет на MQTT retained lifecycle и на безопасное удаление/отключение источников | Средняя |
| Какой lifecycle остается у YAML config bundle после появления `Config Registry`: только import/bootstrap path, аварийный fallback или долгоживущий backoffice-инструмент? | `Config Registry` уже стал source of truth для agent runtime/source config, но нужно явно зафиксировать, какую роль bundle сохраняет в production workflow и support-процедурах | Средняя |

## Observability и эксплуатация

| Вопрос | Почему это важно | Степень блокировки |
| --- | --- | --- |
| Какие health/metrics считаются обязательными для edge runtime и платформы в первом production-срезе? | В конфиге уже есть `metrics_bind`, а в архитектуре есть observability, но минимальный контракт SLI/SLO пока не назван | Средняя |
| Нужно ли в production считать lag по Delivery Outbox, delivery latency и source connection uptime как обязательные SLI? | Эти метрики логично следуют из архитектуры Local State Store и delivery-модели, но без явного решения их легко не реализовать вовремя | Средняя |
| Куда должны уходить логи edge runtime и платформы: только локальный файл/journal или централизованный log sink? | Без этого сложно определить retention, incident workflow и реальную поддержку объекта | Средняя |
| Достаточно ли текущих CLI и demo utilities для диагностики на объекте, или нужен отдельный support-oriented diagnostic mode/UI? | В репозитории уже есть `edge-telemetry-agent check-config`, `show-config`, `enqueue-demo-event`, `deliver-once` и `knx-demo`, но production-support workflow пока не утвержден | Низкая |

## Ближайшие решения

- подтвердить, что текущий `demo-stand` конфиг и ETS-derived артефакты являются каноническим source of truth для первого `KNX`-среза
- проверить доступы internal issue tracker и держать `Post-MVP production foundation`
  backlog синхронизированным с `docs/architecture/decisions.md`
- зафиксировать production MQTT broker, требования по `TLS`/`ACL` и способ хранения секретов
- зафиксировать contract и limits для config delivery: bundle layout, revision generation, Kafka delivery record, retained projection order и rollback semantics
- выбрать cloud provider первого пилота: `VK Cloud` или `Yandex Cloud`
- зафиксировать Kafka topic contract, retention/rollup/deduplication contract для ClickHouse после load PoC
