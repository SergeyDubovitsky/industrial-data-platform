# Hierarchical Catalog V1

Дата: 2026-05-18
Статус: working plan

Этот документ фиксирует candidate capability для `Hierarchical Catalog V1`:
иерархию объектов, источников и точек поверх текущей registry model.

Это не accepted architecture decision и не ADR. Runtime placement и граница с
будущим `Digital Twin Registry` / `Asset Graph Registry` намеренно оставлены
открытыми и вынесены в proposed
[`Draft ADR-015 Proposal: Hierarchical Catalog and Digital Twin boundary`](adrs/ADR-015-hierarchical-catalog-runtime-boundary.md).

## Цель

`Catalog V1` нужен как общий иерархический слой для:

- навигации и authoring workflows рядом с `Config Registry`;
- internal `/backoffice`, где оператору нужна понятная структура объекта;
- будущего presentation layer `Web Monitoring Module`;
- импорта ETS/OPC UA/других source maps в человеко-читаемое дерево.

Catalog может быть реализован как slice внутри `apps/idp_config_registry` или
как отдельный service/package в monorepo. Оба варианта технически реалистичны;
выбор должен зависеть от ownership, consumers, consistency model, target domain
model и runtime lifecycle, а не от сложности scaffold generation.

Storage baseline для вариантов, которые используют PostgreSQL: `Platform Store`.

## Use Case Split

`Catalog V1` не должен подменять собой весь twin-layer.

В этом working plan `Catalog V1` означает navigation/authoring tree:

- дерево для удобной навигации по объектам, источникам и точкам;
- folders и reference nodes на existing registry entities;
- public-code API/backoffice surface;
- lightweight metadata для presentation/navigation needs.

Отдельный future use case — `Digital Twin Registry` / `Asset Graph Registry`:

- объектная модель реального мира;
- arbitrary typed attributes на объектах;
- non-tree relations вроде `partOf`, `locatedIn`, `connectedTo`, `feeds`,
  `poweredBy`, `measures`, `controls`;
- telemetry bindings вида `source.point` / `point_code` / telemetry series ->
  `twin.attribute`;
- unit, quality/status semantics и computed/derived attributes.

Если эти свойства нужны в первом implementation target, scope нужно переименовать
и планировать как первый slice `Digital Twin Registry` / `Asset Graph Registry`,
а не как простой `Hierarchical Catalog V1`.

## Runtime Placement

Placement остается открытой архитектурной развилкой:

- embedded slice внутри `apps/idp_config_registry`;
- отдельный Catalog service/package в monorepo;
- shared library только как вспомогательная code-sharing техника после выбора
  runtime owner.

Если Catalog нужен прежде всего для Config Registry authoring и internal
backoffice, embedded slice может быть прямым стартом. Если Catalog сразу
считается самостоятельной navigation/presentation boundary для нескольких
consumers, отдельный service/package может быть правильным первым target.

Пока решение не принято:

- `decisions.md` не обновляется;
- implementation issue должен сначала выбрать runtime owner;
- LikeC4 placement считается candidate view для обсуждения, а не принятой
  runtime boundary.

## Candidate C4 Placement

В текущем PR LikeC4 может показывать Catalog как candidate C3 component внутри
`industrial-data-platform.idp-config-registry`, чтобы визуализировать embedded
вариант.

Это не запрещает отдельный Catalog service/package. Если команда выберет
отдельный runtime boundary, C4 нужно будет заменить на C2 container для Catalog
и обновить зависимости Config Registry, Backoffice и Web Monitoring.

Candidate C3 view:

- `c3-idp-config-registry-catalog`

## Identity Model

Config Registry использует две разные идентичности:

- PostgreSQL tables имеют internal UUID primary key `id` и UUID foreign keys.
- Domain/API/backoffice workflows работают с public codes:
  `tenant_code`, `asset_code`, `agent_code`, `source_code`, `point_code`.
- Edge/Kafka/MQTT payload contracts остаются на wire names `tenant_id`,
  `asset_id`, `agent_id`, `source_id`, `point_id`; Catalog V1 не меняет эти
  контракты.
- `point_ref` остается техническим адресом точки внутри source, например KNX
  group address, OPC UA node id или register reference.
- `point_key` остается safe representation для MQTT topic path.

Следствие: candidate Catalog API и backoffice forms должны использовать public
codes, а не internal UUID. UUID допустим только как storage key и SQLAdmin row
id.

## V1 Model

Рекомендуемая функциональная модель: один default catalog tree на tenant.

Catalog tree хранит произвольно вложенную hierarchy через adjacency list:

- каждый node принадлежит одному `tenant_code`;
- `parent_node_code` nullable: `null` означает root-level node;
- `node_code` уникален внутри tenant tree;
- `sort_order` задает порядок siblings;
- `display_name` хранит человеко-читаемое имя node;
- `node_type` определяет семантику node.

V1 node types:

- `folder` — чистый организационный раздел без ссылки на registry entity;
- `asset_ref` — presentation reference на asset;
- `agent_ref` — presentation reference на agent;
- `source_ref` — presentation reference на source;
- `point_ref` — presentation reference на point.

Catalog node identity отдельна от registry entity identity. Один asset, source
или point может быть представлен в нескольких местах дерева разными catalog
nodes. Это нужно для разных пользовательских представлений: физическая
топология, этажи/зоны, инженерные системы, арендаторы или эксплуатационные
группы.

## Storage And Query Shape

V1 достаточно adjacency list plus recursive SQL/CTE:

- `catalog_trees`: tenant, tree code, display name, status/timestamps;
- `catalog_nodes`: tree, parent node, node code, node type, display name,
  target public codes, sort order, metadata JSON, timestamps.

Default tree code: `default`.

Recursive CTE используется для:

- чтения всего дерева tenant-а;
- чтения subtree от выбранного node;
- проверки циклов при move/update;
- вычисления path/depth для backoffice и future UI.

Closure table/materialized path не нужны в V1. Их можно добавить после
измерений на реальном размере дерева.

## Candidate API

Candidate Catalog API surface для будущей реализации:

- `GET /tenants/{tenant_code}/catalog/default/tree`
- `POST /tenants/{tenant_code}/catalog/default/nodes`
- `PATCH /tenants/{tenant_code}/catalog/default/nodes/{node_code}`
- `DELETE /tenants/{tenant_code}/catalog/default/nodes/{node_code}`

Если Catalog остается внутри `Config Registry`, эти routes будут частью
Config Registry API. Если команда выбирает отдельный service/package, те же
semantics нужно оформить как Catalog API boundary.

Requests/responses используют public codes. Internal UUID не выходит в API.

Minimal node payload:

- `node_code`
- `parent_node_code`
- `node_type`
- `display_name`
- `sort_order`
- `target`
- `metadata_json`

`target` зависит от `node_type`:

- для `folder`: `null`;
- для `asset_ref`: `asset_code`;
- для `agent_ref`: `asset_code`, `agent_code`;
- для `source_ref`: `asset_code`, `agent_code`, `source_code`;
- для `point_ref`: `point_code`.

## Backoffice Surface

`Catalog V1` должен проектироваться с internal authoring/admin surface, но
текущий SQLAdmin не нужно считать целевым tree editor.

Issue #21 закрепил `/backoffice` как browser-tested workflow и показал важную
деталь: SQLAdmin работает с persisted UUID row ids, а application use cases
работают с public codes. Это полезно для narrow internal CRUD/admin flows, но
плохо покрывает нормальное редактирование дерева.

Для реализации Catalog нужно:

- проводить create/update/delete/move через application use cases или Catalog
  API;
- добавить UUID-to-public-code bridge для SQLAdmin row actions;
- показывать selectors по public codes и readable labels;
- предусмотреть dedicated internal tree UI для navigation, move subtree,
  sibling ordering и validation;
- добавить Playwright coverage для folder/ref node creation, edit/delete,
  subtree/tree read и basic selector flows.

Если Catalog остается embedded slice внутри Config Registry, SQLAdmin может
быть временной internal surface для минимальных tree/node CRUD flows, но не
должен считаться полноценным UI для настройки дерева.

Если Catalog будет отдельным service/package, current Config Registry SQLAdmin
не должен быть UI управления новой иерархией. Нужен отдельный internal UI,
который работает через Catalog API/internal use cases.

## Boundaries

V1 не меняет:

- edge runtime config payloads;
- MQTT topic tree;
- Kafka topics;
- ClickHouse tables/views;
- telemetry read API;
- alarm workflow;
- Keycloak/RBAC model.

V1 как navigation tree не решает:

- `Digital Twin Registry` / `Asset Graph Registry` target model;
- typed object attributes;
- telemetry bindings;
- non-tree semantic relations;
- computed/derived attributes;
- semantic enrichment для Web Monitoring/Alarms.

V1 не решает автоматическое discovery всех tags/models. Importers могут
создавать catalog nodes позже, но discovery policy остается отдельным решением.

## Implementation Notes For Future Issue

Первую implementation issue стоит резать после выбора runtime owner и scope:
navigation tree или target twin/asset graph slice.

- domain entities/value objects для tree/node;
- repository/unit-of-work protocols;
- PostgreSQL models and Alembic migration;
- in-memory adapter для fast tests;
- application use cases для create/update/delete/read tree;
- API router under tenant catalog path;
- backoffice views and selectors;
- package tests, PostgreSQL tests и Playwright backoffice UI tests.

Если Catalog становится accepted boundary, нужно обновить `decisions.md`,
living docs и LikeC4 в соответствии с выбранным runtime placement.

## Open Questions

- Выбираем embedded Config Registry slice или отдельный Catalog service/package
  для первого implementation target?
- Первый target — navigation tree или Digital Twin / Asset Graph slice?
- Нужны ли несколько именованных trees на tenant сразу после default tree?
- Нужны ли arbitrary attributes и telemetry bindings в первом implementation
  issue, или это отдельная future capability?
- Какие relation types нужны target graph: `partOf`, `locatedIn`,
  `connectedTo`, `feeds`, `poweredBy`, `measures`, `controls`?
- Какие import sources первыми создают catalog nodes: synthetic generator,
  ETS/KNX project parser, OPC UA importer или ручной backoffice workflow?
- Нужен ли tenant-facing Catalog API до Keycloak/RBAC, или V1 остается internal
  Config Registry/backoffice surface?
- Какие metadata fields нужны presentation layer beyond `metadata_json`?
