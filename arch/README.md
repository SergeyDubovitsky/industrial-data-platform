# LikeC4 Architecture

В этой директории хранится архитектурная модель в формате LikeC4.

Это source of truth для `C4`-представлений. Все архитектурные схемы и диаграммы в проекте ведутся только в `LikeC4`. Markdown-документы в `docs/architecture/` описывают решения, ограничения, контракты и runtime-сценарии, но не содержат source-диаграмм.

## Файлы

- `package.json` — локальные зависимости и команды для LikeC4 CLI
- `likec4.config.json` — конфигурация LikeC4-проекта
- `likec4/specification.c4` — описание базовых element kinds
- `likec4/model.c4` — архитектурная модель и связи между участниками/системами
- `likec4/views.c4` — представления, начиная с `C1 system context`
- `likec4/deployments/` — deployment model и deployment views
- `likec4/devices/` — модель и `C2` для полевых устройств и контроллеров
- `likec4/gateways/` — модель и `C2` для протокольных шлюзов и SCADA-контроллеров
- `likec4/external-systems/` — внешние облачные интеграции вроде `SMS`, `Email`, `Push`, `Webhook`
- `likec4/systems/edge-telemetry-agent/` — C2-модель `Edge Telemetry Agent`
- `likec4/systems/industrial-data-platform/` — C2-модель `Industrial Data Platform`
- `likec4/systems/web-monitoring-module/` — C2-модель `Web Monitoring Module`
- `likec4/systems/alarm-management-module/` — C2-модель `Alarm Management Module`

Системные файлы workspace и LikeC4-исходники разделены:

- верхний уровень `arch/` — tooling, config, `node_modules`, `dist`
- поддиректория `arch/likec4/` — только `.c4`-источники модели
- поддиректория `arch/likec4/deployments/` — deployment model и deployment views
- поддиректория `arch/likec4/devices/` — полевые устройства и их собственные `C2`-view
- поддиректория `arch/likec4/gateways/` — шлюзы, протокольные сегменты и их `C2`-view
- поддиректория `arch/likec4/external-systems/` — только внешние облачные сервисы
- поддиректория `arch/images/` — локальные SVG-иконки для LikeC4 через alias `@`

Для разрабатываемых систем C2-диаграммы выносятся в отдельные директории:

- `arch/likec4/systems/<system-id>/views.c4` — views конкретной системы
- `arch/likec4/systems/<system-id>/containers/*.c4` — по одному файлу на контейнер

## Текущий scope

Сейчас описаны:

- `C1` системного контекста
- `C2` для `Полевые устройства и контроллеры`
- `C2` для `Протокольные шлюзы и SCADA-контроллеры`
- `C2` для `Edge Telemetry Agent`
- `C2` для `Industrial Data Platform`
- `C2` для `Web Monitoring Module`
- `C2` для `Alarm Management Module`
- `Deployment` для demo-стенда, текущей workstation-based реализации и production-контура Industrial Data Platform с модулями поверх него
- `View` для текущего monitored scope demo-стенда

На уровне `C1` модель фиксирует:

- внешних акторов: `Сервисный инженер`, `Оператор`, `Диспетчер`
- внешние системы: полевые устройства, протокольные шлюзы, каналы уведомлений
- разрабатываемые системы: `Edge Telemetry Agent` на объекте, `Industrial Data Platform` в облаке/интернете и отдельные модули `Web Monitoring Module` / `Alarm Management Module`
- ключевые границы ответственности: edge-сбор на объекте, data platform ingestion/storage в облаке, monitoring UI отдельно, alarm workflow отдельно, notifications через внешние каналы

Модель изначально проектируется как универсальная:

- `KNX`
- `Modbus`
- `OPC UA`
- другие PLC / SCADA / southbound-интеграции

Текущий практический первый адаптер в проекте — `KNX`, но имя и структура модели уже сделаны мультипротокольными.

## Термины

Канонический глоссарий проекта вынесен в
[`docs/architecture/glossary.md`](../docs/architecture/glossary.md).

В `arch/` оставляем только LikeC4-модель, структуру workspace и правила
ведения диаграмм, чтобы не дублировать общую архитектурную терминологию.

## Команды

После установки `Node.js` и зависимостей:

```bash
cd arch
npm install
npm run dev
```

Полезные команды:

- `npm run dev` — локальный preview LikeC4
- `npm run validate` — валидация DSL, семантики и layout
- `npm run build` — собрать статический output
- `npm run export:json` — экспортировать модель в JSON
- `npm run export:mermaid` — экспортировать производное представление в Mermaid
- `npm run mcp` — поднять LikeC4 MCP server

## Текущее состояние окружения

Зависимости `LikeC4` уже установлены локально в `arch/node_modules`, а базовые команды `validate`, `build` и `export:json` успешно отработали на текущей модели.

## Следующий шаг

Следующие логичные шаги для модели:

- дополнительные deployment views для production-вариантов beyond demo-стенда
- при необходимости `C3` для ключевых контейнеров, например `Collector Runtime` и `MQTT Ingestion Gateway`
