# Architecture Docs

Дата: 2026-05-10
Статус: working index

Начинайте отсюда, если нужно быстро понять систему без чтения всех ADR.

## Быстрый вход

| Нужно понять | Читать |
| --- | --- |
| Что система делает сейчас | `current-state.md` |
| Термины и границы понятий | `glossary.md` |
| Какие вопросы еще открыты | `open-questions.md` |
| Какие архитектурные решения активны | `decisions.md` |
| Что принято после MVP по pilot/cloud/OPC UA/issue tracker governance | `current-state.md`, `solution-architecture.md`, `open-questions.md` |
| Где граница между data platform, web monitoring и alarms | `current-state.md`, `decisions.md`, `../../arch/README.md` |
| Целевую архитектуру и runtime-сценарии | `solution-architecture.md` |
| Почему были приняты ключевые решения | `adrs/README.md`, затем archived ADR |
| Точные контракты сообщений, topics и таблиц | `../contracts/README.md` |
| Карты систем и контейнеров | `../../arch/README.md` |

## Правило приоритета

- `current-state.md` описывает рабочую картину на сегодня.
- `decisions.md` является компактным register активных решений.
- `adrs/archive/` объясняет историю решений и trade-off.
- `docs/contracts/` является source of truth для полей сообщений, MQTT/Kafka
  topics, table names и JSON Schema.
- `arch/likec4/` является source of truth для C4-модели систем и контейнеров.
- internal issue tracker является source of truth для execution backlog,
  приоритетов и статусов; git-документация не хранит live execution plans.

Если документы расходятся, сначала проверьте `current-state.md` и
`docs/contracts/`, затем смотрите `decisions.md` и архивные ADR как объяснение
происхождения решения.
