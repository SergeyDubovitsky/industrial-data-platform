# ADR-015: Hierarchical Catalog runtime boundary

Дата: 2026-05-18
Статус: proposed

## Контекст

`Hierarchical Catalog` нужен как слой навигации и представления поверх tenants,
assets, agents, sources и points. Он должен поддержать:

- authoring workflows рядом с `Config Registry`;
- internal `/backoffice` workflows;
- будущий presentation layer `Web Monitoring Module`;
- импорт source maps из synthetic/ETS/OPC UA/других источников.

Это не только вопрос хранения дерева. Catalog может стать отдельной доменной
границей, потому что им будут пользоваться разные поверхности: backend authoring,
internal backoffice и будущие UI/read screens.

Отдельный service/package технически реалистичен уже сейчас. Создание FastAPI
scaffold, package entrypoint, Alembic migrations и CI wiring не является главным
ограничением. Вопрос ADR не в сложности генерации кода, а в том, какая runtime
и data ownership boundary правильная для первого production-grade направления.

## Статус решения

Решение о runtime placement не принято.

Этот ADR фиксирует варианты и критерии выбора, чтобы не закрепить placement
случайно через первый working-plan документ или LikeC4-диаграмму.

## Варианты

### Вариант A: Catalog внутри `apps/idp_config_registry`

Catalog реализуется как component/use-case slice внутри текущего
`idp_config_registry` runtime и хранит state в PostgreSQL `Platform Store`
рядом с registry entities.

Этот вариант уместен, если первый смысл Catalog — authoring/navigation layer для
Config Registry и internal `/backoffice`, а внешние consumers еще не требуют
самостоятельного runtime lifecycle.

Плюсы:

- единая транзакционная граница с registry entities и config authoring;
- простой reuse текущего backoffice, application use cases и public code model;
- меньше межсервисных contracts до стабилизации Catalog use cases.

Риски:

- Catalog может незаметно стать слишком широкой частью Config Registry;
- будущий `Web Monitoring Module` может начать зависеть от Config Registry
  runtime там, где логичнее отдельная read/navigation boundary;
- extraction позже потребует аккуратно вынести schema/API/use cases.

### Вариант B: Catalog как отдельный service/package в монорепо

Catalog получает собственный runtime boundary, API и package, но остается частью
того же monorepo и `Industrial Data Platform`.

Этот вариант уместен, если Catalog сразу считается самостоятельным source of
truth для иерархической навигации, которым пользуются Config Registry,
Backoffice и будущий Web Monitoring как peer consumers.

Плюсы:

- явная ownership boundary и меньше риска расширить Config Registry за пределы
  конфигурационного backend-а;
- проще развивать Catalog API как общий navigation/presentation service;
- будущие permissions, read models и UI consumers можно проектировать вокруг
  Catalog, а не вокруг Config Registry internals.

Риски:

- нужно сразу определить межмодульный contract между Catalog и registry entities;
- понадобится решить consistency model для ссылок на assets/agents/sources/points;
- backoffice integration станет межсервисным workflow, а не локальным
  SQLAdmin/use-case extension.

### Вариант C: Catalog как shared library без собственного runtime

Catalog model, recursive tree logic и validation выносятся в library, которую
используют один или несколько services.

Этот вариант уместен только как code-sharing technique. Он не отвечает сам по
себе на вопрос source of truth, persistence ownership, API ownership и
backoffice workflow.

Плюсы:

- можно переиспользовать модель и validation;
- не нужно сразу выбирать отдельный deployable.

Риски:

- library не является runtime boundary;
- persistence и API ownership все равно придется выбрать отдельно;
- при нескольких consumers легко получить разные state owners поверх одной
  общей модели.

## Критерии выбора

Решение нужно принимать не по тому, насколько быстро сгенерировать scaffold, а
по следующим критериям:

- кто является owner Catalog state: Config Registry или отдельная platform
  navigation boundary;
- является ли Catalog source of truth или только view/authoring helper поверх
  registry entities;
- какие first-class consumers нужны в первом implementation slice:
  `/backoffice`, Config Registry API, Web Monitoring read UI/API или importers;
- нужна ли Catalog API boundary независимо от Config Registry API;
- допустима ли strong consistency с registry entities через одну PostgreSQL
  transaction, или нужна межсервисная consistency model;
- должен ли Catalog иметь независимый deployment lifecycle, permissions model и
  observability.

## Предлагаемая рамка обсуждения

Если ближайший implementation slice — ручное authoring/backoffice поверх
existing registry entities, вариант A может быть самым прямым стартом.

Если команда считает Catalog самостоятельным navigation/presentation product
surface уже сейчас, вариант B стоит рассматривать как первый implementation
target, а не как далекую оптимизацию.

Вариант C можно использовать только как вспомогательную технику после выбора
runtime owner; сам по себе он не закрывает архитектурную развилку.

## Consequences пока решение открыто

- `decisions.md` не обновляется.
- `Hierarchical Catalog V1` остается working plan, а не accepted boundary.
- LikeC4 может показывать только candidate placement для обсуждения, но не
  должен выглядеть как принятое C2/C3 решение.
- Любой future implementation issue должен сначала выбрать runtime owner:
  embedded Config Registry slice или отдельный Catalog service/package.
