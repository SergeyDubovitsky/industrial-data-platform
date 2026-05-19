# Draft ADR-015 Proposal: Hierarchical Catalog and Digital Twin boundary

Дата: 2026-05-19
Статус: draft/proposed, not accepted

Этот документ не является принятым ADR до появления записи в
`docs/architecture/decisions.md`. Он фиксирует proposed architecture decision
material: какие use cases смешиваются под словом `Catalog`, какие референсные
модели стоит учитывать, и какие runtime boundary варианты нужно выбрать перед
первой implementation issue.

## Контекст

В обсуждении `Hierarchical Catalog V1` появились два разных use case.

Первый use case — `Hierarchical Catalog V1` как navigation/authoring slice:

- человеко-читаемое дерево для tenants/assets/agents/sources/points;
- удобная навигация и ручное наполнение рядом с `Config Registry`;
- internal backoffice/admin workflow;
- default tree на tenant, folders и reference nodes;
- public-code API/backoffice surface поверх текущих registry entities.

Второй use case — target `Digital Twin Registry` / `Asset Graph Registry`:

- модель того, что существует в реальном мире и как это связано;
- произвольные доменные атрибуты объектов;
- non-tree relations между объектами;
- связь логического атрибута объекта с технической точкой или telemetry series;
- semantic enrichment для Web Monitoring, Alarms и future analytics.

Эти use cases не равны. `Config Registry` отвечает на вопрос: как edge agent
должен читать и доставлять данные. Target `Digital Twin Registry` / `Asset Graph
Registry` отвечает на вопрос: что существует в реальном мире, как это связано и
какие логические атрибуты можно наблюдать или вычислять.

Отдельный service/package технически реалистичен уже сейчас. Создание FastAPI
scaffold, package entrypoint, Alembic migrations и CI wiring не является главным
ограничением. Вопрос этого draft ADR не в сложности генерации кода, а в том,
какую предметную модель и runtime/data ownership boundary мы выбираем.

## Reference scan

Референсы показывают, что промышленные twin/catalog решения почти всегда
разделяют минимум три слоя: graph/model of things, bindings to telemetry or
state, и application-facing views/API.

| Reference | Что дает для нашей развилки |
| --- | --- |
| [Azure Digital Twins twin graph](https://learn.microsoft.com/en-us/azure/digital-twins/concepts-twins-graph) / [DTDL models](https://learn.microsoft.com/en-us/azure/digital-twins/concepts-models) | Twin — это instance модели, relationships образуют graph. Relationships имеют семантику вроде containment или functional links. Azure также явно отличает twin graph от device twins; telemetry в DTDL не является основным способом хранения incoming device data. |
| [AWS IoT SiteWise asset modeling](https://docs.aws.amazon.com/iot-sitewise/latest/userguide/industrial-asset-models.html) / [asset properties](https://docs.aws.amazon.com/en_us/iot-sitewise/latest/userguide/asset-properties.html) | Asset models, asset hierarchies, attributes, measurements, transforms и metrics являются first-class concepts. Measurement связывается с data stream/property alias и имеет unit/data type. |
| [Cognite Data Fusion industrial knowledge graph](https://docs.cognite.com/api-reference/concepts/data-modeling) / [views](https://docs.cognite.com/api-reference/concepts/views) / [time series](https://docs.cognite.com/dev/concepts/resource_types/timeseries) | CDF отделяет industrial knowledge graph от time series storage. Nodes/edges и flexible schemas моделируют реальность, views дают стабильный API для приложений, time series имеют datapoints, aggregation и status codes. |
| [Eclipse BaSyx architecture](https://eclipse.dev/basyx/architecture/) / [IDTA AAS metamodel](https://industrialdigitaltwin.org/en/?specificationpapers=specification-of-the-asset-administration-shell-part-1-metamodel-idta-number-01001) | AAS дает digital identity asset-а и submodels для static/dynamic data. Dynamic submodels дают unified access to live asset data; RelationshipElement связывает referable/external references. |
| [Eclipse Ditto digital twins](https://eclipse.dev/ditto/intro-digitaltwins.html) / [basic concepts](https://eclipse.dev/ditto/basic-overview.html) | Ditto хорошо иллюстрирует current-state twin as JSON object: attributes для metadata, features/properties для state. Это ближе к latest-state API, чем к богатой industrial asset graph ontology. |
| [ETSI NGSI-LD introduction](https://cim.etsi.org/NGSI-LD/official/introduction.html) / [FIWARE NGSI-LD HowTo](https://fiware.github.io/data-models/specs/ngsi-ld_howto.html) | NGSI-LD строит model вокруг Entity, Property и Relationship в JSON-LD. Properties/relationships могут иметь temporal/metadata-like properties, включая observedAt/unitCode migration patterns. |
| [Brick relationships](https://docs.brickschema.org/brick/relationships.html) | Для building domain есть готовые semantics: entities, points, hasPoint/isPointOf, hasPart, hasLocation, feeds. Points являются telemetry/control representations, а не просто rows в registry. |
| [Project Haystack refs and relationships](https://project-haystack.org/doc/docHaystack/Kinds) / [relationships](https://project-haystack.org/doc/docHaystack/Relationships) | Haystack использует tags, refs и simple filters; relationships кодируются ref tags. Важный lesson: opaque ids + display names + domain tags лучше, чем смешивание display path и identity. |
| [RealEstateCore introduction](https://www.realestatecore.io/introduction/) / [REC modules](https://doc.realestatecore.io/3.3/) | REC описывает building knowledge graphs: BuildingElement, Asset, Point, Sensor/Command/Setpoint, hasPart/isPartOf и отдельные APIs. Это аргумент не изобретать building semantics вслепую, если первый домен будет smart buildings. |

Следствие для нас: простой adjacency tree можно делать как V1 projection, но
target twin-layer требует отдельного словаря понятий: `twin`, `attribute`,
`relationship`, `telemetry binding`, `unit`, `quality/status`, `computed
attribute` и application views.

## Статус решения

Решение о runtime placement и target domain model не принято.

Этот draft ADR фиксирует варианты и критерии выбора, чтобы не закрепить
placement случайно через working-plan документ или LikeC4-диаграмму.

## Предметная развилка

### Use case A: Hierarchical Catalog V1

`Hierarchical Catalog V1` — это минимальный navigation/authoring slice.

Он может хранить:

- catalog tree;
- catalog nodes;
- folders;
- references на existing registry entities через public codes;
- display names, sort order и lightweight metadata.

Он не обязан решать:

- произвольную typed object model;
- telemetry bindings;
- non-tree asset graph;
- semantic enrichment для latest/history API;
- computed attributes;
- domain ontology compatibility.

Если выбираем только этот use case, термин `Catalog` должен оставаться узким:
дерево навигации и authoring projection, а не полноценный twin-layer.

### Use case B: Digital Twin Registry / Asset Graph Registry

Target `Digital Twin Registry` / `Asset Graph Registry` — это отдельная
capability поверх data platform.

Она должна рассматривать как first-class concepts:

- `twin_id` / `twin_code` и `twin_type`;
- arbitrary attributes на объекте;
- `attribute_key` / typed attribute definition;
- non-tree relationships: `partOf`, `locatedIn`, `connectedTo`, `feeds`,
  `poweredBy`, `measures`, `controls`;
- telemetry bindings: `source.point` / `point_code` / telemetry series ->
  `twin.attribute`;
- unit, value type, status/quality semantics;
- computed/derived attributes;
- application views для Web Monitoring, Alarm Management и future UI.

Если команда хочет эти свойства в первом implementation target, это уже не
простой `Catalog V1`; это первый slice `Digital Twin Registry` /
`Asset Graph Registry`, даже если UI начинает с дерева.

## Runtime boundary варианты

### Вариант A: Catalog V1 внутри `apps/idp_config_registry`

Catalog реализуется как component/use-case slice внутри текущего
`idp_config_registry` runtime и хранит state рядом с registry entities.

Этот вариант уместен только если первый scope — navigation/authoring tree для
Config Registry и узкий internal admin workflow.

Плюсы:

- единая транзакционная граница с registry entities и config authoring;
- простой reuse текущих public codes и registry use cases;
- меньше межмодульных contracts до стабилизации tree semantics.

Риски:

- название `Catalog` может незаметно расширить Config Registry до twin-layer;
- Web Monitoring может получить premature dependency на Config Registry;
- будущий вынос в Asset Graph service потребует миграции schema/API/use cases.

### Вариант B: отдельный Catalog/Twin service/package в monorepo

Catalog/Twin получает собственный runtime boundary, API, package и ownership,
но остается частью `Industrial Data Platform` monorepo.

Этот вариант уместен, если первый scope уже включает object attributes,
telemetry bindings, non-tree relations или будущую Web Monitoring/Alarm
semantic API boundary.

Плюсы:

- явная domain ownership boundary;
- не расширяет Config Registry за пределы edge configuration backend-а;
- естественнее для future `Digital Twin Registry` / `Asset Graph Registry`;
- проще дать Web Monitoring/Alarms семантический read boundary.

Риски:

- нужно выбрать consistency model для references на registry entities;
- нужен межмодульный contract между Config Registry и Catalog/Twin;
- backoffice/tree editor должен идти через Catalog API/internal UI, а не через
  локальный SQLAdmin Config Registry.

### Вариант C: shared library без runtime

Library может содержать value objects, validation, import helpers или tree
algorithms.

Этот вариант не отвечает на вопросы source of truth, API ownership, persistence
ownership и UI workflow. Он допустим только как вспомогательная техника после
выбора runtime owner.

## Backoffice и UI implication

Текущий SQLAdmin внутри `Config Registry` подходит для узких internal CRUD/admin
операций и для проверки UUID-to-public-code bridge.

Он плохо подходит как основной редактор дерева или target twin graph:

- навигация по дереву;
- move subtree;
- ordering siblings;
- проверка ссылок;
- работа с атрибутами и telemetry bindings;
- понятный операторский сценарий настройки.

Если выбирается вариант A, SQLAdmin может быть временной internal surface для
минимальных tree/node CRUD flows, но не должен считаться целевым tree editor.

Если выбирается вариант B, нужен отдельный internal Catalog/Twin API и отдельный
internal UI, специально сделанный для редактирования дерева/графа. Config
Registry SQLAdmin может оставаться только adjacent admin surface.

## Telemetry enrichment target flow

Текущий storage/read path остается technical:

1. Edge публикует telemetry с wire/storage ids (`tenant_id`, `asset_id`,
   `source_id`, `point_id`/`point_key`, revisions).
2. Ingestion пишет canonical telemetry в Kafka/ClickHouse.
3. Future enrichment связывает technical series с `twin.attribute`.
4. Web Monitoring и Alarm Management смогут читать latest/history не только по
   raw point, но и по semantic path: `twin_id`/`attribute_key`,
   `twin_type`, unit, location/path и graph relations.

`Read-Only Telemetry API V1` может остаться raw/latest-history API без metadata
joins. Но target design должен оставить место для semantic enrichment, чтобы
не зацементировать Web Monitoring вокруг технических `point_code`/`point_id`
как единственного доменного интерфейса.

## Критерии выбора

Перед implementation issue нужно ответить:

- первый slice — navigation tree или twin/asset graph?
- `Catalog` является source of truth или только view/authoring projection?
- нужны ли arbitrary attributes и telemetry bindings уже в V1?
- нужны ли non-tree relations сразу или достаточно одного tree projection?
- кто first-class consumer: Config Registry, internal UI, Web Monitoring,
  Alarms, importers?
- нужна ли отдельная semantic API boundary независимо от Config Registry?
- допустима ли strong consistency через одну PostgreSQL transaction, или нужна
  межмодульная consistency model?
- должны ли permissions, deployment lifecycle и observability быть независимыми?
- будем ли мы мапиться на Brick/Haystack/RealEstateCore для building domain или
  оставляем собственную минимальную vocabulary до пилота?

## Предлагаемая рамка обсуждения

Если ближайшая задача — только ручная навигация и authoring над existing
registry entities, можно рассматривать `Hierarchical Catalog V1` как узкий
embedded или separate slice, но явно без target twin promises.

Если задача — создать основу для object attributes, telemetry bindings,
semantic monitoring и alarm rules, нужно обсуждать `Digital Twin Registry` /
`Asset Graph Registry` как отдельную domain capability. В этом случае отдельный
service/package должен быть полноценным first option, а не future optimization.

## Consequences пока решение открыто

- `decisions.md` не обновляется.
- `Hierarchical Catalog V1` остается working plan, а не accepted boundary.
- LikeC4 показывает только candidate placement для embedded tree variant.
- Current C2/deployment diagrams не должны добавлять Catalog/Twin как принятый
  dependency или Platform Store state.
- Future implementation issue должен выбрать один из двух стартовых scopes:
  navigation tree или Digital Twin / Asset Graph slice.
