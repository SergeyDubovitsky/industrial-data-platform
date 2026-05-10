# Предварительный анализ: KNX -> OPC UA Bridge и Python OPC Server для SCADA

Дата: 2026-04-18  
Статус: analysis

## 1. Контекст

От заказчика поступил запрос на реализацию программного моста `KNX -> OPC` на
стеке `Python` с интеграцией в `MasterSCADA`.

Ключевые ожидания:

- кроссплатформенный сервер
- импорт `ETS`-проекта для ускорения внедрения
- работа минимум с `10 000` тегов и заделом на рост
- чтение текущих значений через `OPC`
- подписка клиента на изменения значений
- передача управляющих воздействий из `SCADA` в `KNX`
- понятная модель кэша/хранения состояния
- текущая эксплуатационная среда заказчика: `Windows Server 2019`
- контейнерная поставка сервиса в рамках пилота

Дополнительно нужно оценить:

- какие библиотеки использовать для `OPC UA` сервера
- можно ли использовать текущие наработки `Edge Agent`
- есть ли готовые решения на рынке и насколько выгодно `build vs buy`

## 2. Что уже есть в репозитории

### 2.1. Готовые наработки, которые можно переиспользовать

В репозитории уже есть несколько сильных заготовок под задачу:

- `libs/knx_project_parser` умеет читать `ETS .knxproj`
  и извлекать:
  - group addresses
  - `DatapointType`
  - устройства
  - communication assets
  - связи communication assets <-> group addresses
- `apps/knx_demo` уже использует `xknx` для подключения к `KNX/IP`,
  чтения значений и получения telegrams
- `apps/edge_telemetry_agent` уже содержит:
  - protocol-agnostic модель `Observation -> TelemetryEvent`
  - конфигурацию `agent / sources / points`
  - merge source defaults + point overrides
  - локальный `SQLite outbox`
  - фильтрацию по `change_threshold`
  - persistent `agent_id`

### 2.2. Что пока не готово

При этом текущий `Edge Agent` еще не является законченным runtime для новой
задачи:

- в коде есть сильная доменная модель, но нет полноценного `delivery worker`
  и runtime-петли даже для уже выбранного `MQTT`
- текущая архитектура документов рассматривает `OPC UA` в первую очередь как
  southbound-источник данных для чтения агентом, а не как northbound-сервер
  для `SCADA`
- идея `OPC как просто еще один transport рядом с MQTT` слишком упрощает
  задачу: `MQTT` отдает поток событий, а `OPC UA server` экспонирует
  stateful address space, подписки, browse и write semantics

Вывод: текущие наработки очень полезны, но `OPC UA` не стоит проектировать как
буквально еще один `delivery.transport = opcua`.

## 3. Анализ MasterSCADA и протокольной цели

По приложенному документу `MasterSCADA 4D`:

- `MasterSCADA` поддерживает `OPC DA/HDA` и `OPC UA (Client/Server)`
- в составе runtime есть модуль `OPC UA client/server`
- текущая эксплуатационная среда заказчика: `Windows Server 2019`

Для данного проекта это означает:

- для интеграции с текущей `MasterSCADA` достаточно делать сервер именно
  `OPC UA`
- реализация сразу `OPC DA/HDA + OPC UA` не является обязательной для запуска
- `OPC UA` закрывает реальные требования заказчика по чтению, подписке и
  записи, оставаясь кроссплатформенным
- при этом наличие у заказчика `Windows Server 2019` не означает, что именно
  нативная поставка на `Windows` должна входить в первый пилот; контейнерный
  пилот на `Ubuntu Server LTS` можно рассматривать как отдельный целевой
  сценарий поставки и эксплуатации

## 4. Анализ Python-библиотек для OPC сервера

### 4.1. Кандидаты

| Вариант | Статус | Плюсы | Минусы | Вывод |
| --- | --- | --- | --- | --- |
| `asyncua` / `opcua-asyncio` | основной кандидат | pure Python, client+server, async API, subscriptions, methods, encryption, history support, sync-wrapper | проект еще не на `1.0`, часть advanced features ограничена, ниже ceiling по производительности чем у `C` stack | рекомендовать для MVP и production v1 |
| `python-opcua` | старое API | знакомое API, pure Python | развитие перенесено в `opcua-asyncio` | не использовать для нового проекта |
| `open62541` | технический fallback | зрелый `C` stack, кроссплатформенность, сильная репутация, certification story | не Python-native, интеграция в Python резко усложнит решение | рассматривать только если упрёмся в perf/compliance |

### 4.2. Рекомендация по библиотеке

Для первой версии сервера рекомендуется `asyncua`.

Почему:

- библиотека прямо поддерживает `server` и `client`
- есть поддержка:
  - чтения и записи значений
  - monitored items и subscriptions
  - methods
  - encryption и certificate handling
  - history read / history support
- у библиотеки есть hooks на `PreWrite/PostWrite`, что позволяет связать
  запись из `OPC UA` с отправкой команды в `KNX`
- `asyncio` хорошо сочетается с текущим `xknx`, который уже используется в
  репозитории

### 4.3. Почему не `python-opcua`

`python-opcua` не стоит брать в новый дизайн, потому что его upstream прямо
рекомендует переход на `opcua-asyncio`.

### 4.4. Когда может понадобиться `open62541`

`open62541` имеет смысл рассматривать только в одном из следующих сценариев:

- подтвержденный дефицит производительности `asyncua` на целевом железе
- требование к certification path или соответствию специфичным профилям
- необходимость более глубокой работы с `Historical Access`, `Events/Alarms`
  или security-профилями на уровне, где pure Python stack начнет мешать

На старте это преждевременная оптимизация.

## 5. Готовые решения на рынке

### 5.1. Коммерческие решения

Найден как минимум один прямой референсный продукт:

- `NETx Multi Protocol Server` / `NETx KNX OPC Server`

Сильные стороны готового решения:

- импорт `ETS` через собственный `ETS App`
- двунаправленный обмен
- `KNX` + `OPC DA` + `OPC UA`
- продукт уже позиционируется именно как интеграционный сервер между
  `KNX` и `SCADA/BMS`

### 5.2. Практический вывод по build vs buy

Если заказчику критичны:

- быстрый ввод без разработки
- `OPC DA` уже в первой версии
- минимизация технического риска

то коммерческий gateway выглядит сильной альтернативой собственной разработке.

Если заказчику критичны:

- контроль над логикой
- кастомизация namespace и маппинга
- возможность дальше встроить мост в собственный `Edge Agent`
- отсутствие vendor lock-in

то собственная реализация на `Python` оправдана.

## 6. Можно ли использовать текущий Edge Agent

### 6.1. Короткий ответ

Да, но частично.

### 6.2. Что можно использовать прямо сейчас

Из текущего `Edge Agent` имеет смысл переиспользовать:

- модель конфигурации `source / point`
- типизацию сигналов: `command`, `feedback`, `status`, `sensor`
- обработку `Observation`
- `last value` и `change_threshold` логику
- `SQLite` как локальное тех-хранилище
- подход к унификации протоколов

### 6.3. Что не стоит переносить 1:1

Не стоит моделировать `OPC UA` как простой аналог `MQTT` delivery transport.

Причина:

- `MQTT` публикует события в поток
- `OPC UA server` держит живое состояние узлов
- `OPC UA` требует browseable namespace
- `OPC UA` требует write semantics
- `OPC UA` требует server-side обработки client sessions и subscriptions

Это не просто другой канал доставки тех же событий, а другой northbound
контракт. При этом write-path из `OPC` нужно рассматривать как отдельный
control-scope сценарий, не совпадающий с read-only подходом текущего
web-monitoring data path.

### 6.4. Рекомендованный путь переиспользования

Рекомендуется один из двух путей:

1. Быстрый путь для заказчика:
   сделать отдельное приложение `apps/knx_opc_bridge`, переиспользовав
   `knx_project_parser`, паттерны `xknx` и часть доменных моделей `edge_telemetry_agent`.
2. Стратегический путь:
   после стабилизации вынести общую сердцевину в reusable runtime-core и
   поддерживать два northbound-адаптера:
   - `mqtt publisher`
   - `opc ua server`

Для текущей задачи правильнее идти по пути `1`, сохранив совместимость
дизайна с будущим путем `2`.

## 7. Предлагаемая архитектура решения

### 7.1. Компоненты

Предлагаемый состав сервиса:

- `ETS Importer`
  - читает `.knxproj`
  - строит registry точек
  - определяет `DPT`, имена, структуру namespace
  - помечает неоднозначные точки для ручного override
- `KNX Connector`
  - подключается к `KNX/IP`
  - получает telegrams
  - выполняет `read_on_start`
  - выполняет selective `periodic_read` там, где это разрешено
- `Value Normalizer`
  - декодирует значения по `DPT`
  - приводит к scalar-типам для `OPC UA`
- `Live State Cache`
  - хранит текущее значение каждой точки
  - качество
  - timestamp
  - raw payload
  - source of update
  - sequence/version
- `OPC UA Server`
  - экспонирует namespace
  - обслуживает `read`
  - отдает `data change notifications`
  - принимает `write`
- `Command Bridge`
  - валидирует запись из `SCADA`
  - преобразует `OPC UA value -> KNX DPT`
  - отправляет `GroupValueWrite`
  - при наличии feedback-пары ждет подтверждение состояния
- `SQLite Tech Store`
  - хранит snapshot состояния при shutdown/restart
  - журнал ошибок/команд/событий связи
  - не заменяет historian

### 7.2. Почему нужен live cache

Для `OPC UA` live cache обязателен.

Именно он позволяет:

- отвечать на `read` мгновенно
- выдавать текущее значение новым клиентам
- генерировать уведомления по подписке
- не ходить в `KNX` на каждый запрос `SCADA`

### 7.3. Будет ли где-то храниться кэш

Рекомендуемая схема:

- основной runtime cache: `in-memory`
- техническое persistence: `SQLite`

`SQLite` нужен не как архив `HDA`, а как:

- warm restart snapshot
- журнал command/result
- диагностика качества связи
- база для future retry/pending command mechanics

Полноценный historian в первую версию моста не включать.

## 8. Семантика чтения, подписки и записи

### 8.1. Чтение в реальном времени

Поддерживается из коробки:

- клиент читает `OPC UA` variable
- сервер отдает последнее значение из live cache
- при старте сервиса `read_on_start` восстанавливает актуальное состояние для
  whitelisted `feedback/status/sensor`

### 8.2. Подписка на изменения

Поддерживается нативно средствами `OPC UA`:

- клиент создает monitored items
- при обновлении значения соответствующий node получает новое value
- сервер отправляет data change notification

### 8.3. Передача управляющих воздействий

Поддерживается, но только для явно разрешенных точек.

Рекомендуемая модель:

- `feedback/status/sensor` узлы по умолчанию `read-only`
- `command` узлы `writable`
- запись в `command` узел приводит к `KNX GroupValueWrite`

Граница сценария:

- управляющие воздействия допускаются только из внешнего `OPC`-клиента
- write-path не должен трактоваться как разрешение на управление из
  web-monitoring UI/API

Критичное замечание:

в `KNX` очень часто команда и подтверждение состояния приходят по разным group
addresses. Поэтому в конфиге нужно явно моделировать:

- `command point`
- `feedback point`
- опционально `linked_feedback_ref`

Без этого запись будет работать технически, но состояние может быть
неподтвержденным.

## 9. Namespace и модель тегов

### 9.1. Минимальная стратегия

Для первой версии стоит использовать стабильные строковые `NodeId`, например:

- `ns=2;s=knx:ga:0/0/7`
- `ns=2;s=knx:ga:2/0/0`

Преимущества:

- стабильность между рестартами
- предсказуемость при импорте
- простое сопоставление `NodeId <-> KNX group address`

### 9.2. Browsing-структура

Нужно делать не плоский список из 10 000 тегов, а дерево:

- `Objects/KNX`
- далее по `building/area/line/device` если данные извлекаются из `ETS`
- либо fallback по `group address ranges`

Это значительно улучшит usability для `MasterSCADA` и `UaExpert`.

### 9.3. Модель типов

Для `MVP` нужно ограничиться scalar-представлением:

- `bool`
- `int`
- `float`
- `string`

Это хорошо согласуется и с текущими контрактами `edge_telemetry_agent`, и с задачей
интеграции в `SCADA`.

## 10. Импорт ETS-проекта

### 10.1. Что уже покрыто

Текущий `knx_project_parser` уже дает достаточно данных, чтобы сделать импортёр:

- group addresses
- `DatapointType`
- устройства и communication assets
- связи communication assets с group addresses

### 10.2. Что еще нужно допроектировать

Импорт `ETS` не должен сразу писать все в runtime без промежуточной валидации.

Нужен `bridge-config` generator, который:

- строит YAML/JSON registry точек
- маппит `DPT -> value_type / opc_variant_type`
- пытается определить `signal_type`
- помечает ambiguous cases как `manual_override_required`

### 10.3. Практический вывод

Требование заказчика по быстрому внедрению через импорт `ETS` реалистично и
хорошо ложится на уже существующие артефакты репозитория.

## 11. Масштабирование до 10 000 тегов

### 11.1. Что реально ограничивает систему

На практике bottleneck будет не только в числе тегов, а в комбинации факторов:

- число узлов в address space
- частота изменений
- количество подписанных клиентов
- политика безопасности `OPC UA`
- производительность диска для `SQLite`
- железо и ОС сервера

### 11.2. Что нужно сделать в дизайне сразу

- стабильные и легкие `NodeId`
- отсутствие тяжелых объектов на каждую точку сверх необходимого
- один `KNX` connection manager на источник
- минимальный `periodic_read`
- `command` и `feedback` как отдельные точки
- lazy/controlled rebuild namespace при переимпорте `ETS`
- лимиты и метрики по subscription/session count

### 11.3. Что можно ожидать сейчас

Без bench на целевом железе нельзя честно обещать конкретный throughput.

Но архитектурно `10 000` точек достижимы, если:

- большая часть точек меняется не одновременно
- нет агрессивного polling по всем адресам
- сервер работает как stateful cache + subscription engine

## 12. Как тестировать скорость

### 12.1. `UaExpert`

`UaExpert` отлично подходит для:

- функциональной проверки browse/read/write
- проверки subscription behavior
- ручной диагностики namespace

Но `UaExpert` не должен быть единственным инструментом нагрузочного теста.

### 12.2. Правильный benchmark plan

Нужны как минимум три режима теста:

1. `Interop smoke`
   - `UaExpert`
   - `MasterSCADA`
2. `Synthetic write/read benchmark`
   - Python load client на `asyncua`
   - серия тестов на `1k / 5k / 10k` узлов
3. `End-to-end KNX load`
   - реальный `KNX` traffic
   - измерение latency:
     - `KNX telegram -> OPC cache update`
     - `OPC write -> KNX command sent`
     - `OPC write -> feedback received`

### 12.3. Какие метрики измерять

- startup time сервера
- время построения namespace
- RAM/CPU
- p50/p95 latency обновления значения
- количество notifications/sec
- время массового browse
- время reconnect после потери `KNX`

## 13. Вопрос DA/HDA и насколько это трудозатратно

### 13.1. Для текущего проекта

Для текущего проекта поддержку `OPC UA` достаточно считать основной и
обязательной.

### 13.2. Почему `DA/HDA` не стоит включать в v1

`OPC Classic` (`DA/HDA`) основан на `COM/DCOM` и по сути привязан к
`Windows`.

Это означает:

- потерю кроссплатформенности
- отдельную реализацию/обвязку
- более высокий эксплуатационный риск
- сложнее деплой, remote access и security

### 13.3. Практический вывод

Если в будущем появится `SCADA`, поддерживающая только `DA/HDA`, то лучше
рассматривать один из двух путей:

- отдельный `Windows-only` bridge поверх уже готового `OPC UA` сервера
- внешний коммерческий gateway `UA -> DA/HDA`

Не рекомендуется проектировать `DA/HDA` как обязательную часть текущего
Python-кроссплатформенного ядра.

## 14. Рекомендованное решение

### 14.1. Техническое решение

Рекомендуется строить `KNX -> OPC UA bridge` как отдельный сервис на:

- `xknx` для `KNX`
- `asyncua` для `OPC UA server`
- `knx_project_parser` для импорта `ETS`
- `SQLite` для технического persistence

### 14.2. Архитектурное решение

Рекомендуется не пытаться прямо сейчас встроить это как `transport = opcua`
в текущий `edge_telemetry_agent`.

Правильнее:

- сделать отдельный сервис
- переиспользовать existing domain ideas
- оставить дизайн совместимым с будущим выделением общего runtime-core

### 14.3. Продуктовое решение

`OPC UA` делать в первой версии обязательно.  
`OPC DA/HDA` в первую версию не включать.  
Готовые коммерческие решения держать как fallback, если сроки или требования по
`DA/HDA` станут критичнее кастомной разработки.

По сценарию поставки:

- в рамках пилота целевая форма поставки — контейнерная
- целевая платформа пилота — `Ubuntu Server LTS`
- нативную поставку на `Windows Server 2019` рассматривать как отдельный
  проект
- полноценный контур `OPC UA security` не включать в базовый объем пилота;
  рассматривать его как отдельный следующий этап после уточнения требований ИБ

## 15. Поэтапный план реализации

### Sprint 0. Discovery + PoC

Цель:

- быстро подтвердить выбранный стек
- снять риск по `10 000` тегам

Задачи:

- сделать минимальный `asyncua` server с `100 / 1 000 / 10 000` nodes
- поднять `UaExpert` и проверить browse/read/subscriptions
- сделать `xknx -> asyncua` proof of concept на нескольких реальных адресах
- подтвердить контейнерный deployment path для пилота

Результат:

- технический verdict по `asyncua`
- baseline по RAM/CPU/startup

### Sprint 1. Read-only bridge MVP

Цель:

- отдать `KNX` данные в `MasterSCADA` через `OPC UA`

Задачи:

- создать приложение `apps/knx_opc_bridge`
- реализовать конфиг сервиса
- реализовать `KNX connector`
- реализовать `live cache`
- реализовать `OPC UA namespace`
- реализовать import `registry` из YAML
- ручная проверка через `UaExpert`

Результат:

- browse/read/subscription работают
- значения обновляются из `KNX`

### Sprint 2. ETS import

Цель:

- ускорить внедрение

Задачи:

- сделать CLI `knxproj -> bridge-config`
- маппить `DPT -> OPC type`
- строить дерево namespace из `ETS`
- добавить флаги `manual_override_required`

Результат:

- можно быстро загрузить новый объект из `ETS`

### Sprint 3. Write path

Цель:

- поддержать команды из `SCADA` в `KNX`

Задачи:

- реализовать writable command nodes
- реализовать `OPC write -> KNX group write`
- добавить allowlist на write
- добавить `command/feedback` linking
- добавить timeout/ack policy

Результат:

- команды уходят в `KNX`
- feedback корректно отражается в `OPC`

### Sprint 4. Hardening

Цель:

- подготовить к пилотной эксплуатации

Задачи:

- контейнерная дистрибуция для `Ubuntu Server LTS`
- логирование и metrics
- reconnect policy
- warm restart через `SQLite snapshot`
- нагрузочные тесты на `10 000` тегов

Дополнительно вне базового пилота:

- отдельный security-hardening этап для `OPC UA` после уточнения требований ИБ
  (`TLS`, certificates, trust list, client auth)

Результат:

- сервис готов к контейнерному пилоту

## 16. Главные риски

- не для всех точек `ETS` можно автоматически и безопасно определить
  `signal_type`
- запись в `KNX` опасна без четкой whitelist-модели и связи с feedback
- `10 000` тегов могут упереться не в библиотеку, а в hardware profile,
  security mode и число клиентов
- если заказчик внезапно потребует `DA/HDA` в `v1`, трудозатраты резко вырастут
- текущий `Edge Agent` придется аккуратно развести с новым northbound-сценарием,
  чтобы не запутать архитектуру

## 17. Открытые вопросы к заказчику

- нужен ли после базового пилота отдельный этап `OPC UA security`, или для
  пилота допустим `NoSecurity` во внутреннем сегменте
- нужны ли исторические данные через `OPC UA Historical Access` или достаточно
  только real-time
- сколько одновременно ожидается клиентов `OPC UA`
- какие группы точек действительно должны быть writable
- требуется ли hot-reimport `ETS` без перезапуска сервиса

## 18. Итоговый вывод

Принять в качестве базового решения:

- `KNX -> OPC UA bridge` как отдельный Python-сервис
- `asyncua` как основную библиотеку `OPC UA server`
- `xknx` как основной runtime-коннектор к `KNX`
- `knx_project_parser` как основу импорта `ETS`
- `SQLite` как техническое кэш/сервисное хранилище

Не включать в первую версию:

- `OPC DA/HDA`
- попытку встроить `OPC UA` как простой аналог `MQTT transport`
- полноценный historian

## 19. Источники

- Исходные данные заказчика: <https://docs.google.com/spreadsheets/d/144zhEZWdqdr7HlBMIItDnE5nbK4Grqx0jLlftVGNRmI/edit?gid=0#gid=0>
- `MasterSCADA 4D` спецификация: <https://support.insat.ru/demo/Documentation/Manual/MasterSCADA_4D/SpecificationMasterSCADA_4D.pdf>
- `MasterSCADA 4D` официальный продуктовый раздел: <https://insat.ru/products/scada/>
- `asyncua` PyPI: <https://pypi.org/project/asyncua/>
- `asyncua` GitHub: <https://github.com/FreeOpcUa/opcua-asyncio>
- `python-opcua` PyPI: <https://pypi.org/project/opcua/>
- `python-opcua` GitHub: <https://github.com/FreeOpcUa/python-opcua>
- `OPC Foundation` про `OPC Classic`: <https://opcfoundation.org/about/opc-technologies/opc-classic/>
- `OPC Foundation Reference`: <https://reference.opcfoundation.org/>
- `KNX Association` про `ETS`: <https://support.knx.org/hc/en-us/articles/21037139544722-What-is-ETS-Engineering-Tool-Software>
- `KNX Association` про `ETS6`: <https://www.knx.org/knx-en/for-professionals/software/>
- `UaExpert` официальный сайт: <https://www.unified-automation.com/products/development-tools/uaexpert.html>
- `Microsoft Learn` про поддержку контейнеров на `Windows Server`: <https://learn.microsoft.com/en-us/troubleshoot/windows-server/containers/support-for-windows-containers-docker-on-premises-scenarios>
- `open62541`: <https://www.open62541.org/>
- `NETx Multi Protocol Server` на сайте KNX: <https://www.knx.org/knx-en/newsroom/en/news/NETx-Multi-Protocol-Server/>
- `NETx` interfaces / ETS import / OPC: <https://www.netxautomation.com/server-systems/netx-mp-server/20-functions-interfaces>
