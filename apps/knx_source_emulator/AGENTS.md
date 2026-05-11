# KNX Source Emulator Guide

Scope: `apps/knx_source_emulator/`.

This package is a local dev/test southbound emulator for `edge_telemetry_agent`.
It consumes generated models from `idp_synthetic_config` and exposes KNX-like
events to the real edge runtime.

## Do

- Keep `knx-source-emulator` and `knx_source_emulator` scoped to local/dev and
  integration scenarios.
- Use `idp_synthetic_config` for catalog generation, Config Registry seeding,
  point ids, group addresses, value profiles, names, and descriptions.
- Keep runtime orchestration async-first with `asyncio`; do not create a
  thread per point.
- Keep MQTT telemetry publication in `edge_telemetry_agent`, not in the
  emulator.

## Do Not

- Do not duplicate Config Registry client/seeding logic from
  `idp_synthetic_config`.
- Do not treat the phase-1 JSON-lines adapter as production KNXnet/IP
  compatibility.
- Do not change `idp/v1` MQTT contracts or Kafka/ClickHouse contracts from this
  package.

## Validation

- `uv run --package knx-source-emulator pytest apps/knx_source_emulator/tests`
- For the full local path, also validate the affected
  `edge_telemetry_agent` tests and relevant integration tests.

