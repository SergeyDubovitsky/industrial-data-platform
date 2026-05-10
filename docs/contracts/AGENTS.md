# Contracts Guide

Scope: `docs/contracts/`.

This directory is the canonical source of truth for wire, topic, schema, and
storage contracts.

## Do

- Keep contract ids versioned.
- Preserve backward compatibility within a `v1` contract.
- Add a new version for breaking changes.
- Keep MQTT/Kafka/ClickHouse names aligned with tests and migrations.
- Update app guides only after the canonical contract is updated.

## Do Not

- Do not rename `idp.*` topics or message ids as part of product naming.
- Do not change ClickHouse table names without migration and compatibility
  planning.
- Do not let ADR prose override schema or table details in this directory.

## Validation

- Run affected package and integration tests from `docs/agents/module-map.yaml`.
- For schema changes, run the tests that validate or produce the changed
  payloads.
