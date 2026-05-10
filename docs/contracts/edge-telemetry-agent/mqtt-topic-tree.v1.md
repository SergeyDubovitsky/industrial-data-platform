# `idp.edge.mqtt.topic-tree.v1`

Дата: 2026-05-02
Статус: working draft

Этот контракт фиксирует MQTT topic tree, которым владеет `edge_telemetry_agent`
как реализованный edge-модуль.
Payload-схемы находятся в `schemas/`.

## Корневой префикс

```text
idp/v1
```

## Topic templates

Текущий runtime уже публикует `event`. Остальные topic types ниже остаются
каноническим target contract и могут быть реализованы отдельным runtime шагом.

| Topic type | Topic template | Message contract | QoS | Retain | Expiry | Когда публикуется |
| --- | --- | --- | --- | --- | --- | --- |
| `agent-runtime-config` | `idp/v1/agents/{agent_id}/config/agent-runtime` | `idp.edge.agent-runtime-config.v1` | `1` | `true` | нет | Config delivery projection материализует root agent runtime config агента |
| `source-config` | `idp/v1/agents/{agent_id}/sources/{source_id}/config` | `idp.edge.source-config.v1` | `1` | `true` | нет | Config delivery projection материализует config конкретного source |
| `config-status` | `idp/v1/agents/{agent_id}/status/config` | `idp.edge.config.status.v1` | `1` | `true` | нет | Target contract: edge-telemetry-agent сообщает pending/applied/rejected config revision |
| `event` | `idp/v1/assets/{asset_id}/agents/{agent_id}/sources/{source_id}/points/{point_key}/event` | `idp.edge.telemetry.event.v1` | `1` | `false` | `telemetry_message_expiry_seconds` | Реализовано: публикуется, когда point прошел publish filter |
| `connection` | `idp/v1/assets/{asset_id}/agents/{agent_id}/sources/{source_id}/status/connection` | `idp.edge.source.connection.v1` | `1` | `true` | нет | Target contract: при изменении состояния southbound source |
| `lwt` | `idp/v1/assets/{asset_id}/agents/{agent_id}/status/lwt` | `idp.edge.agent.lwt.v1` | `1` | `true` | нет | Target contract: `offline` публикует broker как Will, `online` публикует агент после connect |

## Routing rules

- `asset_id`, `agent_id`, `source_id` и каждый segment `topic_root` должны соответствовать `mqtt_path_id`.
- `mqtt_path_id` pattern: `^[a-z0-9][a-z0-9_-]{0,127}$`.
- `point_key` строится как обратимое percent-encoding от `point_ref`.
- `point_key` должен быть одним MQTT topic segment и соответствовать pattern `^(?:[A-Za-z0-9._~-]|%[0-9A-F]{2})+$`.
- `point_key` не может содержать `/`, `+`, `#`, whitespace или неполные percent-escape последовательности.
- Для telemetry routing identity берется из topic path, а `tenant_id` берется из payload и валидируется ingestion-слоем.
- Source metadata приходит из retained `idp.edge.source-config.v1`.
- MQTT broker не является source of truth для текущего состояния точки; текущее состояние строится backend-ом из событий и хранилищ.

## Publish policy

- Telemetry event публикуется как один MQTT `PUBLISH` на одну точку.
- Batch payload на уровне source не используется.
- Per-point retained `state` topic не используется.
- Per-point retained `meta` topics не используются.
- Agent runtime config не публикуется edge-telemetry-agent-ом: retained MQTT topics строятся platform projection pipeline из Kafka config delivery records.
- Publisher уже использует MQTT 5 `Content Type = application/json`.
- `Topic Alias` остается planned optimization: контракт его рекомендует, но текущий publisher еще не использует alias negotiation.
