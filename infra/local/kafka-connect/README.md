# Local Kafka Connect

This directory contains the local Kafka Connect image and versioned connector
config for the `Kafka -> ClickHouse` Industrial Data Platform Telemetry Store
path.

The connector is installed into the image at build time:

```bash
docker compose --env-file ../../.env build kafka-connect
```

`CLICKHOUSE_KAFKA_CONNECT_VERSION` defaults to `latest` for the local MVP
because the current Confluent Hub client successfully resolves `latest` but
rejects the explicit version string it reports. At the time this was verified,
`latest` downloaded ClickHouse connector `v1.3.7`.

The connector config is applied through the repeatable bootstrap script:

```bash
uv run --env-file .env python infra/local/kafka-connect/bootstrap_connector.py
```

MVP assumptions:

- `value.converter` and `key.converter` are
  `org.apache.kafka.connect.storage.StringConverter`.
- Raw Kafka values are wrapped into the landing `payload_json` column through
  Kafka Connect `HoistField$Value`.
- `exactlyOnce=false`.
- Connector-level errors are routed to `idp.telemetry-store.dlq.v1`.
- Domain mapping stays out of Kafka Connect and is handled by ClickHouse
  materialized views in the next implementation slice.
