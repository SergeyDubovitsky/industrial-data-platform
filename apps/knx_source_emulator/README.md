# knx-source-emulator

Local KNX-like southbound source emulator for synthetic
`edge_telemetry_agent` scenarios.

The package consumes `idp_synthetic_config` generated models and Config Registry
seeding summaries. It does not publish MQTT telemetry directly; the real Edge
Telemetry Agent connects to the emulator, processes observations, writes its
SQLite state/outbox, and delivers MQTT telemetry events through the existing
edge path.

Phase 1 uses a small asyncio JSON-lines adapter boundary for local/dev tests
instead of a full KNXnet/IP server. The source config remains `source_type=knx`
with `connection.mode=synthetic`, so production MQTT/Kafka/ClickHouse contracts
do not change.

## CLI

```bash
uv run --package knx-source-emulator knx-source-emulator plan --dry-run
uv run --package knx-source-emulator knx-source-emulator seed-config
uv run --package knx-source-emulator knx-source-emulator run
uv run --package knx-source-emulator knx-source-emulator start
```

Default generation is intentionally small for local smoke runs: `3` devices and
`10` tags per device. The upper local load/dev profile remains `100 x 100` and
is validated by `idp_synthetic_config`.

