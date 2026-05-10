# Local Infrastructure Guide

Scope: `infra/local/`.

This directory contains the local Industrial Data Platform stack and the local
Web Monitoring Grafana surface used by development and integration tests.

## Do

- Keep Docker service and image names stable.
- Keep local infrastructure close to contract behavior, even when it is not a
  production topology.
- Update integration fixtures when compose services, ports, or readiness
  behavior change.
- Keep Grafana under Web Monitoring Module ownership.

## Do Not

- Do not treat the local compose project as the production deployment target.
- Do not switch broker runtime from Apache Kafka to Redpanda broker without the
  dedicated compatibility PoC.
- Do not move domain parsing from ClickHouse materialized views into Kafka
  Connect SMTs without an ADR or explicit plan.

## Validation

- `docker compose -f infra/local/compose.yaml config --quiet`
- `uv run --group integration pytest tests/integration/test_config_registry_kafka_publisher.py tests/integration/test_kafka_to_clickhouse_storage.py tests/integration/test_grafana_clickhouse.py`
