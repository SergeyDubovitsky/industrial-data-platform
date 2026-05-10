# ADR-013: Post-MVP product, pilot and execution governance

Дата: 2026-05-05
Статус: accepted

Примечание 2026-05-10: `ADR-014` уточняет продуктовую архитектуру: ядро теперь
называется `Industrial Data Platform`, а web monitoring и alarms являются
отдельными модулями поверх него. Решения этого ADR по cloud-first pilot,
OPC UA read-only ingestion, local Docker infra и issue tracker governance остаются
действующими.

## Контекст

Проект уже достиг `MVP baseline` и дальше развивается как самостоятельный
продукт `Industrial Edge Web Monitoring`, а не как заказная разработка под один
объект.

У команды есть возможность позже заходить в более крупные промышленные контуры,
но сначала нужно обкатать систему на реальных `KNX`-объектах: проверить сбор
данных, веб-отображение, историю, тревоги и эксплуатационные сценарии.

При этом:

- product/IP остаются за командой проекта;
- эксклюзив под одного пилотного заказчика или объект не принимается;
- управление оборудованием не входит в web-monitoring scope первого этапа;
- on-prem/self-hosted инфраструктура первых заказчиков пока не готова;
- локальная Docker-инфра уже стала критичной для разработки и integration
  проверки;
- последние архитектурные и продуктовые решения принимались в документации и
  переписке, а не через internal issue tracker;
- в текущем issue tracker есть внешние участники/первые заказчики, поэтому его
  нельзя без ограничений использовать для внутреннего backlog, стратегии,
  коммерции и security decisions.

## Решение

### Product и pilot direction

`Industrial Edge Web Monitoring` развивается как самостоятельный продукт.
Пилотные заказчики/партнеры могут давать реальные объекты, доступы,
`KNX`-карты или описание сигналов и обратную связь, но не получают эксклюзив на
продукт или долю в product/IP.

Коммерческая роль партнера может фиксироваться как доля с продаж по клиентам,
которых партнер привел и помогает сопровождать. Это не является долей в
продукте или правами на IP.

Первый validation track:

- реальные `KNX`-объекты;
- cloud web monitoring;
- сначала сбор и отображение данных;
- затем история, минимальный alarm lifecycle и нормальные operator screens;
- без управляющих команд из web-monitoring UI/API;
- без обязательного on-prem/self-hosted deployment на первом этапе.

### Deployment

Первый пилот разворачивается cloud-first в российском облаке.
Приоритетные кандидаты:

- `VK Cloud`;
- `Yandex Cloud`.

Причина: основные ожидаемые заказчики находятся в РФ, а on-prem/self-hosted
инфраструктура первых пилотных заказчиков пока не готова.

`self-hosted`/on-prem остается целевым deployment mode продукта, но переносится
после cloud validation и готовности инфраструктуры заказчика.

Cloud и future self-hosted должны оставаться двумя deployment modes одной
платформы. Provider-specific детали не должны протекать в:

- MQTT/Kafka topic names;
- message schemas;
- ClickHouse table names и migrations;
- config revision model;
- agent runtime/source config contracts;
- acceptance tests основного data path.

Локальная `Docker Compose` infra остается обязательной для разработки,
integration-тестов, smoke-тестов, onboarding и воспроизведения инцидентов. Она
не является production target первого пилота, но должна оставаться максимально
близкой к cloud/self-hosted baseline по contracts, migrations и operational
semantics.

### Protocol roadmap

`KNX` остается первым validation protocol на реальных объектах.

Следующий protocol track после `KNX`:

- `OPC UA read-only ingestion`;
- `edge_telemetry_agent` работает как `OPC UA client`;
- агент только считывает данные из `OPC UA server`;
- `OPC UA` nodes мапятся в существующую `source/point` model;
- telemetry идет по существующему path `MQTT -> Kafka -> ClickHouse`.

В первый `OPC UA` ingestion slice не входят:

- управляющие команды из web-monitoring UI/API;
- `OPC UA server` mode внутри web-monitoring platform;
- `OPC UA Historical Access`;
- `OPC DA`;
- попытка моделировать `OPC UA` как простой delivery transport вместо
  southbound protocol.

Под `write` в этом ADR понимаются именно управляющие команды в промышленный
контур, инициированные web-monitoring UI/API. Это не запрещает штатные
platform writes: сохранение telemetry/status records, config revisions,
outbox records, audit records, alarm state и operator workflow state.

`Modbus TCP` остается возможным future adapter, но не является выбранным
следующим protocol track.

### Platform scope после MVP

Текущий реализованный backend-срез — `Config Registry`.

Полный tenant-facing `Platform API` остается future boundary и будет
проектироваться отдельными ADR. Текущий `Config Registry` не должен незаметно
расширяться до auth/alarm/telemetry read API без отдельного решения.

Минимальный post-MVP production-foundation scope:

- cloud-first `KNX` pilot;
- production scope `Config Registry` / future `Platform API`;
- MQTT security baseline;
- `ClickHouse` load PoC как gate перед production DDL/TTL/rollups/retention;
- минимальный alarm lifecycle: `active/raised`, `acknowledged`,
  `cleared/resolved`, `severity`;
- config delivery limits/contracts;
- первые operator screens.

Термин `M1` не принимается как официальный milestone. Для документации
используется формулировка `post-MVP production-foundation increment`.

### Documentation и issue tracker governance

Принимается гибридная модель source of truth:

- git-документация и ADR являются source of truth для архитектурных решений,
  product boundaries, long-lived rationale, contracts и open questions;
- internal issue tracker является source of truth для execution backlog,
  приоритетов, статусов, follow-up задач и будущего анализа выполнения.

Issue tracker для execution backlog должен быть internal-only для команды
проекта.

Первые заказчики, партнеры и внешние участники не должны иметь доступ к
внутреннему project/backlog, где видны:

- internal roadmap;
- commercial terms;
- product/IP strategy;
- security decisions;
- raw implementation backlog;
- незрелые hypotheses и trade-offs.

Для внешней обратной связи допускаются только безопасные варианты:

- удалить внешних участников из internal issue tracker project и переносить их
  feedback вручную;
- создать отдельный customer-facing project/helpdesk/view только для
  feedback/requests/bugs без internal fields и без видимости внутреннего
  roadmap.

После принятия этого ADR нужно backfill-нуть последние решения в internal issue
tracker.

Минимальный backfill:

- epic/task `Post-MVP production foundation`;
- cloud-first pilot;
- Russian cloud provider selection: `VK Cloud` vs `Yandex Cloud`;
- local Docker infra as required development/test baseline;
- `KNX` cloud pilot;
- `OPC UA read-only ingestion`;
- MQTT security baseline;
- alarm lifecycle minimum;
- `ClickHouse` load PoC;
- `Config Registry` / future `Platform API` scope;
- note that these decisions were made before the issue tracker was re-aligned and are
  now backfilled from ADR/docs.

## Рассмотренные варианты

| Вариант | Решение |
| --- | --- |
| Только git-документация без internal issue tracker | Отклонено. Не дает удобного execution backlog, статусов, follow-up задач и анализа выполнения. |
| Issue tracker как единый source of truth для всего, включая ADR/product strategy | Отклонено. Архитектурные решения и long-lived rationale должны жить рядом с кодом и контрактами. |
| Один общий issue tracker для внутренней команды и первых заказчиков | Отклонено. Внешние участники не должны видеть internal roadmap, commercial terms, IP strategy, security decisions и незрелый backlog. |
| Internal-only issue tracker + git docs/ADR | Принято. Разводит execution management и архитектурную память без утечки внутренней информации. |
| Customer-facing issue tracker project/helpdesk поверх internal project | Допустимо. Только если видимость строго ограничена feedback/requests/bugs и нет доступа к internal fields/backlog. |

## Последствия

Положительные:

- решения по post-MVP направлению становятся проверяемыми и не теряются в
  переписке;
- customer feedback можно учитывать без раскрытия внутреннего backlog;
- local Docker infra остается first-class частью developer workflow;
- cloud-first pilot не ломает будущий self-hosted/on-prem mode;
- `OPC UA` roadmap получает четкий read-only ingestion scope.

Отрицательные:

- нужно перенастроить доступы в internal issue tracker;
- нужно вручную backfill-нуть последние решения в backlog;
- customer-facing feedback workflow потребует отдельной дисциплины triage;
- provider selection `VK Cloud` vs `Yandex Cloud` остается отдельной задачей.

## Проверки принятия

- README говорит про internal issue tracker, а не про общий issue tracker для всех
  участников.
- `docs/architecture/open-questions.md` не держит как открытые те решения,
  которые приняты этим ADR.
- В документах явно различаются local Docker infra, cloud-first pilot и future
  self-hosted/on-prem deployment.
- `OPC UA` описан как read-only southbound ingestion без управляющих команд из
  web-monitoring UI/API, а не как `OPC UA server` mode web-monitoring platform.
- В internal issue tracker создан или обновлен backlog по минимальному backfill
  списку из этого ADR.
- Внешние участники не имеют доступа к internal roadmap/security/commercial/IP
  материалам в internal issue tracker.
