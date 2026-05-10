# knx_demo

Workspace member with small KNX demo utilities for bus reads and blink
patterns.

## Commands

```bash
test -f .env || cp .env.example .env
uv sync
uv run --package knx-demo knx-demo --help
uv run --env-file .env --package knx-demo knx-demo read-signals --help
uv run --env-file .env --package knx-demo knx-demo blink-melody --help
uv run --package knx-demo pytest apps/knx_demo/tests
```

## Subcommands

- `knx-demo read-signals` — send `GroupValueRead` requests and log direct or
  passive updates
- `knx-demo blink-melody` — blink a KNX light with a recognizable rhythm and
  log feedback

Если не передавать `--gateway-ip` и `--gateway-port`, demo-профили читают
значения из переменных окружения (`KNX_LOCAL_*` и `KNX_EXTERNAL_*`).
В monorepo их удобнее передавать через `uv run --env-file .env`.

Текущий default profile в CLI: `external`.
Он соответствует рабочему сценарию с этой workstation через NAT endpoint demo-стенда.
Для запуска из локальной сети объекта явно указывайте `--profile local`.
