# Config Registry Agent Guide

Scope: `apps/idp_config_registry/`.

This package is the Industrial Data Platform Config Registry. It owns
tenant/asset/agent/source/point registry state, rendered edge config revisions,
and Kafka-first config delivery outbox publishing.

## Do

- Keep the existing package, import path, CLI, Docker service, and image names.
- Preserve the clean architecture direction: API routers call application use
  cases; application code depends on ports; infrastructure implements ports.
- Keep PostgreSQL migrations forward-only.
- Keep JSON Schema validation aligned with `docs/contracts/edge-telemetry-agent`.
- Update Config Registry docs when API, backoffice, outbox, or persistence
  behavior changes.

## Do Not

- Do not rename `idp_config_registry` or `idp-config-registry`.
- Do not bypass application use cases from API/backoffice paths.
- Do not write directly to outbox state from presentation code.
- Do not change edge config contract ids without a contract versioning plan.

## Validation

- `uv run --package idp-config-registry pytest apps/idp_config_registry/tests`
- For Kafka/outbox behavior:
  `uv run --group integration pytest tests/integration/test_config_registry_kafka_publisher.py`
