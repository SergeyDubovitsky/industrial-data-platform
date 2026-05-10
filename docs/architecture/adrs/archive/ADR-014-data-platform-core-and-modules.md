# ADR-014: Data Platform core and module boundaries

Дата: 2026-05-10
Статус: accepted

## Контекст

Текущий репозиторий уже фактически реализует ядро сбора и хранения данных:

- `edge_telemetry_agent` собирает telemetry рядом с объектом и надежно доставляет события;
- `Config Registry` хранит tenants/assets/agents/sources/points и выпускает edge config delivery records;
- `MQTT -> Redpanda Connect -> Kafka Event Log -> Kafka Connect -> ClickHouse`
  является рабочим local storage/read path;
- `Telemetry Store` и read models уже используются Grafana и integration-тестами.

При этом документация и C4-модель называли центральную систему
`Monitoring & Alarm Platform`, смешивая три разные ответственности:

- сбор, доставка, хранение, контракты и конфигурация данных;
- web monitoring: dashboards, history и operator read UI;
- alarm management: правила, lifecycle, workflow и notifications.

Такое смешение мешает развивать систему как data platform с независимыми
прикладными модулями поверх нее.

## Решение

Центральное ядро системы теперь называется `Industrial Data Platform`.

`Industrial Data Platform` отвечает за:

- northbound ingestion от edge agents;
- server-issued edge config delivery;
- canonical Kafka-compatible event log;
- source config snapshots и enrichment contracts;
- durable storage/read models на ClickHouse;
- transactional registry/config state на PostgreSQL;
- shared identity/platform services, пока они не выделены отдельным ADR.

`Web Monitoring Module` является отдельным прикладным модулем поверх data platform.
Он отвечает за dashboards, history views, latest values, operator read screens и
read-only visualization. Текущий Grafana surface относится к этому модулю.

`Alarm Management Module` является отдельным прикладным модулем поверх data
platform. Он отвечает за rule engine, alarm lifecycle, acknowledgements,
mutes/operator workflow и notification routing. `alarm_history_events_v1` в
ClickHouse остается storage sink в `Telemetry Store`, но writer/owner этого
потока — `Alarm Management Module`.

`Monitoring & Alarm Platform` больше не используется как имя новой центральной
системы. Это deprecated composite boundary для исторических документов, где
раньше вместе назывались data platform, monitoring UI и alarm workflow.

## Совместимость и reset

Итоговый pre-production reset удаляет старые `wm*` runtime identifiers и не
поддерживает совместимость со старыми локальными topics, storage state или
migration history.

Канонические identifiers после reset:

- Python packages и entrypoints: `edge_telemetry_agent`, `idp_config_registry`,
  `idp_telemetry_store`;
- Docker Compose service names и image names;
- MQTT topic tree `idp/v1/...`;
- Kafka topics `idp.*`;
- contract ids `idp.edge.*`, `idp.*`, `idp.telemetry-store.clickhouse.*`;
- ClickHouse table names сохраняются, если они уже domain-neutral; migration
  history начинается с fresh baseline.

Префикс `idp.*` остается стабильным wire-prefix и означает platform
boundary в контрактах, а не старое продуктовое имя `Monitoring & Alarm Platform`.
Его изменение после reset потребует новых версий контрактов.

## Последствия

Положительные:

- C4-модель отражает реальные границы: data core отдельно, monitoring отдельно,
  alarms отдельно.
- Следующие backend/UI инкременты можно планировать по модулям, не расширяя
  `Config Registry` незаметно до всей платформы.
- Storage, ingestion и contract work можно делать независимо от UX/alarm scope.

Отрицательные:

- В старых ADR останется исторический термин `Monitoring & Alarm Platform`.
- Локальные `wm*` topics, volumes, ClickHouse/Postgres state и migration
  history требуют destructive reset в development окружении.

## Проверки принятия

- LikeC4 содержит `Industrial Data Platform`, `Web Monitoring Module` и
  `Alarm Management Module` как отдельные developed systems.
- `Grafana` и future monitoring frontend находятся в `Web Monitoring Module`.
- `Alarm Rule Engine` и `Notification Service` находятся в
  `Alarm Management Module`.
- `Config Registry`, ingestion, Kafka Event Log, storage writer, ClickHouse и
  PostgreSQL остаются в `Industrial Data Platform`.
- Контрактная документация и runtime paths используют `idp.*`/`idp/v1` без
  старых `wm*` compatibility aliases.
