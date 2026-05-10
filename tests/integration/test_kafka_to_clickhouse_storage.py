from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.integration_storage,
    pytest.mark.integration_data_platform,
]
REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.integration_smoke
def test_kafka_connect_writes_raw_json_to_clickhouse_landing_and_contract_table(
    local_storage_stack,
) -> None:
    payload = {
        "message_type": "idp.telemetry.event.v1",
        "tenant_id": "tenant-storage-it",
        "event_id": "storage-raw-001",
        "idempotency_key": "tenant-storage-it|asset-storage-it|agent-storage-it|storage-raw-001",
        "asset_id": "asset-storage-it",
        "agent_id": "agent-storage-it",
        "source_id": "source-storage-it",
        "source_type": "knx",
        "point_id": "tenant-storage-it|asset-storage-it|source-storage-it|temperature",
        "point_key": "temperature",
        "point_ref": "1/2/3",
        "source_config_revision": "rev-storage-it-001",
        "ts": "2026-05-03T05:50:00Z",
        "ingested_at": "2026-05-03T05:50:01Z",
        "event_type": "telemetry.sample",
        "observation_mode": "listen",
        "value_type": "number",
        "value": 42.5,
        "quality": "good",
        "sequence": 1,
    }
    payload_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))

    local_storage_stack.clickhouse_query("TRUNCATE TABLE kafka_telemetry_events_raw_v1")
    local_storage_stack.clickhouse_query("TRUNCATE TABLE telemetry_events_v1")
    local_storage_stack.produce_kafka_text(
        "idp.telemetry.events.v1",
        payload_json,
    )

    stored_payload = local_storage_stack.wait_for_clickhouse_value(
        """
        SELECT payload_json
        FROM kafka_telemetry_events_raw_v1
        WHERE payload_json LIKE '%storage-raw-001%'
        ORDER BY ingested_at DESC
        LIMIT 1
        FORMAT TabSeparatedRaw
        """.strip()
    )

    assert stored_payload == payload_json

    contract_row = local_storage_stack.wait_for_clickhouse_value(
        """
        SELECT
            tenant_id,
            event_id,
            source_type,
            value_type,
            value_float,
            value_bool,
            value_string
        FROM telemetry_events_v1
        WHERE event_id = 'storage-raw-001'
        FORMAT TabSeparatedRaw
        """.strip()
    )

    assert contract_row == (
        "tenant-storage-it\tstorage-raw-001\tknx\tnumber\t42.5\t\\N\t\\N"
    )

    local_storage_stack.produce_kafka_text(
        "idp.telemetry.events.v1",
        payload_json,
    )
    duplicate_raw_count = local_storage_stack.wait_for_clickhouse_value(
        """
        SELECT count()
        FROM kafka_telemetry_events_raw_v1
        WHERE payload_json LIKE '%storage-raw-001%'
        HAVING count() >= 2
        FORMAT TabSeparatedRaw
        """.strip()
    )
    deduplicated_count = local_storage_stack.clickhouse_query(
        """
        SELECT count()
        FROM telemetry_events_v1 FINAL
        WHERE event_id = 'storage-raw-001'
        FORMAT TabSeparatedRaw
        """.strip()
    ).stdout.strip()

    assert duplicate_raw_count == "2"
    assert deduplicated_count == "1"

    deduplicated_view_count = local_storage_stack.clickhouse_query(
        """
        SELECT count()
        FROM telemetry_events_dedup_v1
        WHERE event_id = 'storage-raw-001'
        FORMAT TabSeparatedRaw
        """.strip()
    ).stdout.strip()
    latest_row = local_storage_stack.clickhouse_query(
        """
        SELECT event_id, value_type, value_float
        FROM telemetry_latest_v1
        WHERE tenant_id = 'tenant-storage-it'
          AND asset_id = 'asset-storage-it'
          AND source_id = 'source-storage-it'
          AND point_key = 'temperature'
        FORMAT TabSeparatedRaw
        """.strip()
    ).stdout.strip()
    minute_rollup_row = local_storage_stack.clickhouse_query(
        """
        SELECT event_count, good_count, number_count, value_min, value_max, value_avg, value_last
        FROM telemetry_1m_v1
        WHERE tenant_id = 'tenant-storage-it'
          AND asset_id = 'asset-storage-it'
          AND source_id = 'source-storage-it'
          AND point_key = 'temperature'
          AND bucket_start = toDateTime('2026-05-03 05:50:00', 'UTC')
        FORMAT TabSeparatedRaw
        """.strip()
    ).stdout.strip()
    hourly_rollup_row = local_storage_stack.clickhouse_query(
        """
        SELECT event_count, good_count, number_count, value_min, value_max, value_avg, value_last
        FROM telemetry_1h_v1
        WHERE tenant_id = 'tenant-storage-it'
          AND asset_id = 'asset-storage-it'
          AND source_id = 'source-storage-it'
          AND point_key = 'temperature'
          AND bucket_start = toDateTime('2026-05-03 05:00:00', 'UTC')
        FORMAT TabSeparatedRaw
        """.strip()
    ).stdout.strip()

    assert deduplicated_view_count == "1"
    assert latest_row == "storage-raw-001\tnumber\t42.5"
    assert minute_rollup_row == "1\t1\t1\t42.5\t42.5\t42.5\t42.5"
    assert hourly_rollup_row == "1\t1\t1\t42.5\t42.5\t42.5\t42.5"

    source_config_payload = {
        "message_type": "idp.source.config.v1",
        "tenant_id": "tenant-storage-it",
        "asset_id": "asset-storage-it",
        "agent_id": "agent-storage-it",
        "source_id": "source-storage-it",
        "source_type": "knx",
        "source_config_revision": "rev-storage-it-001",
        "ts": "2026-05-03T05:50:02Z",
        "ingested_at": "2026-05-03T05:50:03Z",
        "points": [
            {
                "point_id": "tenant-storage-it|asset-storage-it|source-storage-it|temperature",
                "point_key": "temperature",
                "point_ref": "1/2/3",
                "name": "Temperature",
                "signal_type": "sensor",
                "value_type": "number",
                "value_model": "temperature",
            }
        ],
    }
    source_config_json = json.dumps(
        source_config_payload,
        ensure_ascii=True,
        separators=(",", ":"),
    )
    local_storage_stack.produce_kafka_text(
        "idp.source.configs.v1",
        source_config_json,
        key="tenant-storage-it|asset-storage-it|agent-storage-it|source-storage-it",
    )
    source_config_row = local_storage_stack.wait_for_clickhouse_value(
        """
        SELECT source_type, points_json
        FROM source_config_snapshots_v1
        WHERE source_config_revision = 'rev-storage-it-001'
        FORMAT TabSeparatedRaw
        """.strip()
    )
    assert source_config_row == (
        'knx\t[{"point_id":"tenant-storage-it|asset-storage-it|source-storage-it|temperature",'
        '"point_key":"temperature","point_ref":"1/2/3","name":"Temperature",'
        '"signal_type":"sensor","value_type":"number","value_model":"temperature"}]'
    )

    replayed_source_config_payload = {
        **source_config_payload,
        "ingested_at": "2026-05-03T05:50:04Z",
    }
    local_storage_stack.produce_kafka_text(
        "idp.source.configs.v1",
        json.dumps(
            replayed_source_config_payload,
            ensure_ascii=True,
            separators=(",", ":"),
        ),
        key="tenant-storage-it|asset-storage-it|agent-storage-it|source-storage-it",
    )
    duplicate_source_config_count = local_storage_stack.wait_for_clickhouse_value(
        """
        SELECT count()
        FROM kafka_source_configs_raw_v1
        WHERE payload_json LIKE '%rev-storage-it-001%'
        HAVING count() >= 2
        FORMAT TabSeparatedRaw
        """.strip()
    )
    deduplicated_source_config_count = local_storage_stack.clickhouse_query(
        """
        SELECT count()
        FROM source_config_snapshots_v1 FINAL
        WHERE source_config_revision = 'rev-storage-it-001'
        FORMAT TabSeparatedRaw
        """.strip()
    ).stdout.strip()

    assert duplicate_source_config_count == "2"
    assert deduplicated_source_config_count == "1"

    source_connection_payload = {
        "message_type": "idp.source.connection.v1",
        "tenant_id": "tenant-storage-it",
        "asset_id": "asset-storage-it",
        "agent_id": "agent-storage-it",
        "source_id": "source-storage-it",
        "state": "connected",
        "reason": None,
        "ts": "2026-05-03T05:50:04Z",
        "ingested_at": "2026-05-03T05:50:05Z",
    }
    local_storage_stack.produce_kafka_text(
        "idp.source.connections.v1",
        json.dumps(source_connection_payload, ensure_ascii=True, separators=(",", ":")),
        key="tenant-storage-it|asset-storage-it|agent-storage-it|source-storage-it",
    )
    source_connection_row = local_storage_stack.wait_for_clickhouse_value(
        """
        SELECT state, reason
        FROM source_connection_events_v1
        WHERE source_id = 'source-storage-it'
        FORMAT TabSeparatedRaw
        """.strip()
    )
    assert source_connection_row == "connected\t\\N"

    agent_status_payload = {
        "message_type": "idp.agent.status.v1",
        "tenant_id": "tenant-storage-it",
        "asset_id": "asset-storage-it",
        "agent_id": "agent-storage-it",
        "status": "online",
        "ts": "2026-05-03T05:50:06Z",
        "ingested_at": "2026-05-03T05:50:07Z",
    }
    local_storage_stack.produce_kafka_text(
        "idp.agent.status.v1",
        json.dumps(agent_status_payload, ensure_ascii=True, separators=(",", ":")),
        key="tenant-storage-it|asset-storage-it|agent-storage-it",
    )
    agent_status_row = local_storage_stack.wait_for_clickhouse_value(
        """
        SELECT status
        FROM agent_status_events_v1
        WHERE agent_id = 'agent-storage-it'
        FORMAT TabSeparatedRaw
        """.strip()
    )
    assert agent_status_row == "online"

    derived_payload = {
        "message_type": "idp.derived.event.v1",
        "tenant_id": "tenant-storage-it",
        "derived_event_id": "derived-storage-001",
        "idempotency_key": "tenant-storage-it|asset-storage-it|derived-storage-001",
        "asset_id": "asset-storage-it",
        "rule_or_metric_id": "metric-temperature-high",
        "event_type": "derived.metric",
        "ts": "2026-05-03T05:50:08Z",
        "produced_at": "2026-05-03T05:50:09Z",
        "value_type": "boolean",
        "value": True,
        "source_event_ids": ["storage-raw-001"],
        "attributes": {"threshold": 40.0},
    }
    local_storage_stack.produce_kafka_text(
        "idp.derived.events.v1",
        json.dumps(derived_payload, ensure_ascii=True, separators=(",", ":")),
        key="tenant-storage-it|asset-storage-it|metric-temperature-high",
    )
    derived_row = local_storage_stack.wait_for_clickhouse_value(
        """
        SELECT value_type, value_float, value_bool, value_string, source_event_ids_json, attributes_json
        FROM derived_events_v1
        WHERE derived_event_id = 'derived-storage-001'
        FORMAT TabSeparatedRaw
        """.strip()
    )
    assert derived_row == 'boolean\t\\N\ttrue\t\\N\t["storage-raw-001"]\t{"threshold":40}'

    load_poc_result = subprocess.run(
        [
            "uv",
            "run",
            "--env-file",
            str(local_storage_stack.env_file),
            "idp-telemetry-store",
            "load-poc",
            "telemetry-read-models",
            "--rows",
            "2000",
            "--points",
            "20",
            "--batch-size",
            "1000",
            "--duplicate-every",
            "10",
            "--run-id",
            "storage-it-load-poc",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert load_poc_result.returncode == 0, load_poc_result.stderr
    load_poc = json.loads(load_poc_result.stdout)

    assert load_poc["logical_rows"] == 2000
    assert load_poc["duplicate_rows"] == 200
    assert load_poc["inserted_rows"] == 2200
    assert load_poc["queries"]["dedup_count"]["value"] == 2000
    assert load_poc["queries"]["latest_count"]["value"] == 20
    assert load_poc["queries"]["minute_rollup"]["value"] == 2000
    assert load_poc["queries"]["hour_rollup"]["value"] == 2000


def test_invalid_storage_record_goes_to_kafka_connect_dlq(local_storage_stack) -> None:
    invalid_payload = {
        "message_type": "idp.telemetry.event.v1",
        "tenant_id": "tenant-storage-it",
        "event_id": "storage-invalid-001",
        "idempotency_key": "tenant-storage-it|asset-storage-it|agent-storage-it|storage-invalid-001",
        "asset_id": "asset-storage-it",
        "agent_id": "agent-storage-it",
        "source_id": "source-storage-it",
        "source_type": "knx",
        "point_id": "tenant-storage-it|asset-storage-it|source-storage-it|temperature",
        "point_key": "temperature",
        "point_ref": "1/2/3",
        "source_config_revision": "rev-storage-it-001",
        "ts": "2026-05-03T05:50:00Z",
        "ingested_at": "2026-05-03T05:50:01Z",
        "event_type": "telemetry.sample",
        "observation_mode": "listen",
        "value_type": "number",
        "value": "not-a-number",
        "quality": "good",
        "sequence": 1,
    }
    payload_json = json.dumps(invalid_payload, ensure_ascii=True, separators=(",", ":"))

    local_storage_stack.clickhouse_query("TRUNCATE TABLE telemetry_events_v1")
    local_storage_stack.produce_kafka_text(
        "idp.telemetry.events.v1",
        payload_json,
    )

    _key, dlq_payload = local_storage_stack.consume_kafka_json(
        "idp.telemetry-store.dlq.v1",
        predicate=lambda _key, payload: payload.get("event_id")
        == "storage-invalid-001",
        timeout=60,
    )
    row_count = local_storage_stack.clickhouse_query(
        """
        SELECT count()
        FROM telemetry_events_v1
        WHERE event_id = 'storage-invalid-001'
        FORMAT TabSeparatedRaw
        """.strip()
    ).stdout.strip()

    assert dlq_payload["event_id"] == "storage-invalid-001"
    assert row_count == "0"
