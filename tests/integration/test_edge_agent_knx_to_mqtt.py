from __future__ import annotations

import json
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path

import paho.mqtt.client as mqtt
import pytest
import yaml

from edge_telemetry_agent.application.configuration import load_agent_runtime_config
from edge_telemetry_agent.application.delivery import DeliveryWorker
from edge_telemetry_agent.application.processing import ObservationProcessor
from edge_telemetry_agent.domain.events import Observation
from edge_telemetry_agent.infrastructure.mqtt_publisher import connect_mqtt_publisher
from edge_telemetry_agent.infrastructure.sqlite_outbox import SQLiteOutbox
from idp_demo_stack.bundle import load_bundle
from idp_demo_stack.models import TopicScope
from idp_demo_stack.scenario import agent_runtime_config_payload, source_config_payload

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_BUNDLE_PATH = REPO_ROOT / "environments" / "demo-stand" / "edge_telemetry_agent" / "config.bundle.yaml"
KAFKA_SCHEMAS_ROOT = REPO_ROOT / "docs" / "contracts" / "kafka" / "schemas"


@pytest.mark.integration_smoke
@pytest.mark.integration_storage
def test_demo_knx_edge_delivery_flow_reaches_mqtt_kafka_and_clickhouse(
    local_storage_stack,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MQTT_USERNAME", local_storage_stack.mqtt_username)
    monkeypatch.setenv("MQTT_PASSWORD", local_storage_stack.mqtt_password)
    monkeypatch.setenv("KNX_LOCAL_GATEWAY_IP", "127.0.0.1")
    monkeypatch.setenv("KNX_LOCAL_GATEWAY_PORT", "3671")
    monkeypatch.setenv("KNX_LOCAL_ROUTE_BACK", "false")

    bundle = load_bundle(DEMO_BUNDLE_PATH)
    bootstrap_path = _write_bootstrap_config(
        tmp_path,
        agent_id=bundle.agent_id,
        broker=f"mqtt://127.0.0.1:{local_storage_stack.mqtt_port}",
    )
    _seed_config_delivery_records(local_stack=local_storage_stack, bundle=bundle)

    point = bundle.source("knx_main").points[2]
    topic = (
        f"idp/v1/assets/{bundle.asset_id}/agents/{bundle.agent_id}"
        f"/sources/knx_main/points/{point.point_key}/event"
    )
    connected = threading.Event()
    received = threading.Event()
    subscribed = threading.Event()
    received_payloads: list[dict[str, object]] = []

    subscriber = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    subscriber.username_pw_set(
        local_storage_stack.mqtt_username,
        local_storage_stack.mqtt_password,
    )

    def on_message(
        client: mqtt.Client,
        userdata: object,
        message: mqtt.MQTTMessage,
    ) -> None:
        received_payloads.append(json.loads(message.payload.decode("utf-8")))
        received.set()

    def on_connect(
        client: mqtt.Client,
        userdata: object,
        flags: mqtt.ConnectFlags,
        reason_code: mqtt.ReasonCode,
        properties: mqtt.Properties | None,
    ) -> None:
        connected.set()

    def on_subscribe(
        client: mqtt.Client,
        userdata: object,
        mid: int,
        reason_code_list: object,
        properties: object,
    ) -> None:
        subscribed.set()

    subscriber.on_message = on_message
    subscriber.on_connect = on_connect
    subscriber.on_subscribe = on_subscribe
    subscriber.connect("127.0.0.1", local_storage_stack.mqtt_port, keepalive=20)
    subscriber.loop_start()
    assert connected.wait(timeout=10), "MQTT subscriber did not connect in time"
    subscriber.subscribe(topic, qos=1)
    assert subscribed.wait(timeout=10), "MQTT subscriber did not subscribe in time"

    runtime = load_agent_runtime_config(bootstrap_path)
    processor = ObservationProcessor(runtime, agent_id=runtime.agent_id)
    observed_at = datetime.now(tz=UTC).replace(microsecond=0)
    result = processor.process(
        Observation(
            source_id="knx_main",
            point_ref=point.point_ref,
            observation_mode="listen",
            value=24.8,
            value_raw="24.8",
            observed_at=observed_at,
        )
    )
    assert result.event is not None

    outbox = SQLiteOutbox(runtime.storage.sqlite_path)
    outbox.initialize()
    record_id = outbox.append(result.event, available_at=observed_at)
    assert _outbox_row(runtime.storage.sqlite_path, record_id) == ("pending", 0)

    publisher = connect_mqtt_publisher(runtime.delivery.mqtt, agent_id=runtime.agent_id)
    worker = DeliveryWorker(
        runtime_config=runtime,
        agent_id=runtime.agent_id,
        outbox=outbox,
        publisher=publisher,
    )
    try:
        delivery_result = worker.deliver_once(now=observed_at)
        assert delivery_result.reserved_count == 1
        assert delivery_result.published_count == 1
        assert delivery_result.retry_count == 0
        assert delivery_result.dead_letter_count == 0
        assert _outbox_row(runtime.storage.sqlite_path, record_id) == ("sent", 1)
        assert received.wait(timeout=10), "MQTT subscriber did not receive outbox event"
        assert received_payloads[0]["message_type"] == "idp.edge.telemetry.event.v1"
        assert received_payloads[0]["tenant_id"] == bundle.tenant_id
        assert received_payloads[0]["event_type"] == "telemetry.sample"
        assert received_payloads[0]["source_config_revision"] == "rev-demo-stand-knx-main-001"
        assert received_payloads[0]["value"] == 24.8

        kafka_key, kafka_payload = local_storage_stack.consume_kafka_json(
            "idp.telemetry.events.v1",
            expected_key=(
                f"{bundle.tenant_id}|{bundle.asset_id}|knx_main|{point.point_key}"
            ),
        )
        _assert_schema_subset(
            kafka_payload,
            KAFKA_SCHEMAS_ROOT / "idp.telemetry.event.v1.schema.json",
        )
        assert kafka_key == f"{bundle.tenant_id}|{bundle.asset_id}|knx_main|{point.point_key}"
        assert kafka_payload["message_type"] == "idp.telemetry.event.v1"
        assert kafka_payload["tenant_id"] == bundle.tenant_id
        assert kafka_payload["asset_id"] == bundle.asset_id
        assert kafka_payload["agent_id"] == bundle.agent_id
        assert kafka_payload["source_id"] == "knx_main"
        assert kafka_payload["source_type"] == "knx"
        assert kafka_payload["source_config_revision"] == "rev-demo-stand-knx-main-001"
        assert kafka_payload["point_id"] == (
            f"{bundle.tenant_id}|{bundle.asset_id}|knx_main|{point.point_key}"
        )
        assert kafka_payload["point_ref"] == point.point_ref
        assert kafka_payload["value"] == 24.8
        assert kafka_payload["quality"] == "good"

        clickhouse_row = local_storage_stack.wait_for_clickhouse_value(
            f"""
            SELECT tenant_id, asset_id, agent_id, source_id, point_key, value_type, value_float
            FROM telemetry_events_v1
            WHERE event_id = '{kafka_payload["event_id"]}'
            FORMAT TabSeparatedRaw
            """.strip()
        )
        assert clickhouse_row == (
            f"{bundle.tenant_id}\t{bundle.asset_id}\t{bundle.agent_id}"
            f"\tknx_main\t{point.point_key}\tnumber\t24.8"
        )
    finally:
        publisher.close()
        subscriber.disconnect()
        subscriber.loop_stop()


def test_mqtt_to_kafka_ingestion_routes_unresolved_telemetry_to_error_topic(
    local_platform_stack,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KNX_LOCAL_GATEWAY_IP", "127.0.0.1")
    monkeypatch.setenv("KNX_LOCAL_GATEWAY_PORT", "3671")
    monkeypatch.setenv("KNX_LOCAL_ROUTE_BACK", "false")

    bundle = load_bundle(DEMO_BUNDLE_PATH)
    _seed_config_delivery_records(local_stack=local_platform_stack, bundle=bundle)

    point = bundle.source("knx_main").points[2]
    scope = TopicScope(
        topic_root="idp/v1",
        asset_id=bundle.asset_id,
        agent_id=bundle.agent_id,
    )
    publish_json_message(
        host="127.0.0.1",
        port=local_platform_stack.mqtt_port,
        username=local_platform_stack.mqtt_username,
        password=local_platform_stack.mqtt_password,
        topic=scope.point_topic("knx_main", point.point_key, "event"),
        payload={
            "message_type": "idp.edge.telemetry.event.v1",
            "tenant_id": bundle.tenant_id,
            "event_id": "bad-source-config-revision",
            "event_type": "telemetry.sample",
            "source_config_revision": "missing-source-config-revision",
            "ts": "2026-05-02T12:00:00Z",
            "observation_mode": "listen",
            "value": 24.8,
            "value_raw": "24.8",
            "quality": "good",
            "sequence": 1,
        },
    )

    kafka_key, kafka_payload = local_platform_stack.consume_kafka_json(
        "idp.ingestion.errors.v1",
        expected_key=(
            f"{bundle.asset_id}|{bundle.agent_id}|knx_main|idp.edge.telemetry.event.v1"
        ),
    )
    _assert_schema_subset(
        kafka_payload,
        KAFKA_SCHEMAS_ROOT / "idp.ingestion.error.v1.schema.json",
    )
    assert kafka_key == (
        f"{bundle.asset_id}|{bundle.agent_id}|knx_main|idp.edge.telemetry.event.v1"
    )
    assert kafka_payload["message_type"] == "idp.ingestion.error.v1"
    assert kafka_payload["reason_code"] == "source_config_revision_missing"
    assert kafka_payload["mqtt_topic"] == scope.point_topic(
        "knx_main", point.point_key, "event"
    )
    assert kafka_payload["message_type_in"] == "idp.edge.telemetry.event.v1"
    assert kafka_payload["asset_id"] == bundle.asset_id
    assert kafka_payload["agent_id"] == bundle.agent_id
    assert kafka_payload["source_id"] == "knx_main"
    assert kafka_payload["point_key"] == point.point_key


def test_mqtt_to_kafka_status_ingestion_does_not_require_config_cache(
    local_platform_stack,
) -> None:
    scope = TopicScope(
        topic_root="idp/v1",
        asset_id="demo-stand-01",
        agent_id="demo-stand-local",
    )

    publish_json_message(
        host="127.0.0.1",
        port=local_platform_stack.mqtt_port,
        username=local_platform_stack.mqtt_username,
        password=local_platform_stack.mqtt_password,
        topic=scope.source_status_topic("knx_main"),
        payload={
            "message_type": "idp.edge.source.connection.v1",
            "tenant_id": "demo-tenant",
            "state": "connected",
            "ts": "2026-05-02T12:00:00Z",
        },
        retain=True,
    )
    publish_json_message(
        host="127.0.0.1",
        port=local_platform_stack.mqtt_port,
        username=local_platform_stack.mqtt_username,
        password=local_platform_stack.mqtt_password,
        topic=scope.agent_lwt_topic(),
        payload={
            "message_type": "idp.edge.agent.lwt.v1",
            "tenant_id": "demo-tenant",
            "status": "online",
            "ts": "2026-05-02T12:00:00Z",
        },
        retain=True,
    )

    source_key, source_payload = local_platform_stack.consume_kafka_json(
        "idp.source.connections.v1",
        expected_key="demo-tenant|demo-stand-01|demo-stand-local|knx_main",
    )
    _assert_schema_subset(
        source_payload,
        KAFKA_SCHEMAS_ROOT / "idp.source.connection.v1.schema.json",
    )
    assert source_key == "demo-tenant|demo-stand-01|demo-stand-local|knx_main"
    assert source_payload["tenant_id"] == "demo-tenant"
    assert source_payload["state"] == "connected"

    agent_key, agent_payload = local_platform_stack.consume_kafka_json(
        "idp.agent.status.v1",
        expected_key="demo-tenant|demo-stand-01|demo-stand-local",
    )
    _assert_schema_subset(
        agent_payload,
        KAFKA_SCHEMAS_ROOT / "idp.agent.status.v1.schema.json",
    )
    assert agent_key == "demo-tenant|demo-stand-01|demo-stand-local"
    assert agent_payload["tenant_id"] == "demo-tenant"
    assert agent_payload["status"] == "online"


def _outbox_row(sqlite_path: Path, record_id: int) -> tuple[str, int]:
    with sqlite3.connect(sqlite_path) as connection:
        row = connection.execute(
            "SELECT status, attempt_count FROM outbox WHERE id = ?",
            (record_id,),
        ).fetchone()
    if row is None:
        raise AssertionError(f"Outbox record {record_id} was not found")
    return str(row[0]), int(row[1])


def _assert_schema_subset(payload: dict[str, object], schema_path: Path) -> None:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    properties = schema["properties"]
    required = set(schema.get("required", []))

    missing = required - payload.keys()
    if missing:
        raise AssertionError(f"{schema_path.name}: missing required fields {missing}")

    if schema.get("additionalProperties") is False:
        extra = payload.keys() - properties.keys()
        if extra:
            raise AssertionError(f"{schema_path.name}: unexpected fields {extra}")

    for field, value in payload.items():
        field_schema = properties[field]
        if "const" in field_schema and value != field_schema["const"]:
            raise AssertionError(
                f"{schema_path.name}: {field} must be {field_schema['const']!r}"
            )
        if "enum" in field_schema and value not in field_schema["enum"]:
            raise AssertionError(
                f"{schema_path.name}: {field}={value!r} is outside enum"
            )
        _assert_json_type(schema_path=schema_path, field=field, value=value, schema=field_schema)


def _assert_json_type(
    *,
    schema_path: Path,
    field: str,
    value: object,
    schema: dict[str, object],
) -> None:
    expected = schema.get("type")
    if expected is None:
        return

    expected_types = expected if isinstance(expected, list) else [expected]
    if any(_matches_json_type(value, expected_type) for expected_type in expected_types):
        return

    raise AssertionError(
        f"{schema_path.name}: {field}={value!r} does not match type {expected!r}"
    )


def _matches_json_type(value: object, expected_type: object) -> bool:
    match expected_type:
        case "null":
            return value is None
        case "boolean":
            return isinstance(value, bool)
        case "integer":
            return isinstance(value, int) and not isinstance(value, bool)
        case "number":
            return (isinstance(value, int | float) and not isinstance(value, bool))
        case "string":
            return isinstance(value, str)
        case "object":
            return isinstance(value, dict)
        case "array":
            return isinstance(value, list)
        case _:
            raise AssertionError(f"Unsupported schema type {expected_type!r}")


def _seed_config_delivery_records(*, local_stack, bundle) -> None:
    settings = type("BundleSettings", (), {"bundle": bundle})()
    scope = TopicScope(
        topic_root="idp/v1",
        asset_id=bundle.asset_id,
        agent_id=bundle.agent_id,
    )
    agent_runtime_payload = agent_runtime_config_payload(settings)
    runtime_record = _config_delivery_record(
        bundle=bundle,
        config_scope="agent_runtime",
        source_id=None,
        source_config_revision=None,
        target_mqtt_topic=scope.agent_runtime_config_topic(),
        payload_message_type="idp.edge.agent-runtime-config.v1",
        payload=agent_runtime_payload,
    )
    local_stack.produce_kafka_text(
        "idp.edge.configs.v1",
        json.dumps(runtime_record, ensure_ascii=True, separators=(",", ":")),
        key=f"{bundle.tenant_id}|{bundle.asset_id}|{bundle.agent_id}|agent_runtime",
    )
    runtime_message = local_stack.wait_for_retained_mqtt_json(
        scope.agent_runtime_config_topic()
    )
    assert runtime_message.retained is True
    assert runtime_message.payload["config_revision"] == bundle.config_revision

    for source in bundle.sources:
        source_payload = source_config_payload(settings, source=source)
        source_topic = scope.source_config_topic(source.source_id)
        source_record = _config_delivery_record(
            bundle=bundle,
            config_scope=f"source:{source.source_id}",
            source_id=source.source_id,
            source_config_revision=source.source_config_revision,
            target_mqtt_topic=source_topic,
            payload_message_type="idp.edge.source-config.v1",
            payload=source_payload,
        )
        local_stack.produce_kafka_text(
            "idp.edge.configs.v1",
            json.dumps(source_record, ensure_ascii=True, separators=(",", ":")),
            key=(
                f"{bundle.tenant_id}|{bundle.asset_id}|{bundle.agent_id}"
                f"|source:{source.source_id}"
            ),
        )
        source_message = local_stack.wait_for_retained_mqtt_json(source_topic)
        assert source_message.retained is True
        assert source_message.payload["source_config_revision"] == (
            source.source_config_revision
        )


def _config_delivery_record(
    *,
    bundle,
    config_scope: str,
    source_id: str | None,
    source_config_revision: str | None,
    target_mqtt_topic: str,
    payload_message_type: str,
    payload: dict[str, object],
) -> dict[str, object]:
    idempotency_scope = config_scope.replace(":", "|")
    return {
        "message_type": "idp.edge.config.delivery.v1",
        "tenant_id": bundle.tenant_id,
        "asset_id": bundle.asset_id,
        "agent_id": bundle.agent_id,
        "config_revision": bundle.config_revision,
        "config_scope": config_scope,
        "source_id": source_id,
        "source_config_revision": source_config_revision,
        "target_mqtt_topic": target_mqtt_topic,
        "mqtt_retain": True,
        "mqtt_qos": 1,
        "operation": "upsert",
        "payload_message_type": payload_message_type,
        "payload": payload,
        "idempotency_key": (
            f"{bundle.tenant_id}|{bundle.asset_id}|{bundle.agent_id}|"
            f"{bundle.config_revision}|{idempotency_scope}"
        ),
        "issued_at": bundle.issued_at,
    }


def publish_json_message(
    *,
    host: str,
    port: int,
    username: str,
    password: str,
    topic: str,
    payload: dict[str, object],
    retain: bool = False,
) -> None:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.username_pw_set(username, password)
    client.connect(host, port, keepalive=20)
    client.loop_start()
    try:
        message_info = client.publish(topic, json.dumps(payload), qos=1, retain=retain)
        message_info.wait_for_publish(timeout=10)
        if not message_info.is_published():
            raise AssertionError("MQTT publish did not complete within 10 seconds.")
        if message_info.rc != mqtt.MQTT_ERR_SUCCESS:
            raise AssertionError(f"MQTT publish failed with rc={message_info.rc}.")
    finally:
        client.disconnect()
        client.loop_stop()


def _write_bootstrap_config(
    tmp_path: Path,
    *,
    agent_id: str,
    broker: str,
) -> Path:
    bootstrap_path = tmp_path / "bootstrap.yaml"
    payload = {
        "agent_id": agent_id,
        "delivery": {
            "transport": "mqtt",
            "mqtt": {
                "enabled": True,
                "version": "5.0",
                "broker": broker,
                "topic_root": "idp/v1",
                "client_id_prefix": "edge-telemetry-agent-it",
                "username_env": "MQTT_USERNAME",
                "password_env": "MQTT_PASSWORD",
                "qos": 1,
                "clean_start": True,
                "session_expiry_seconds": 0,
                "telemetry_message_expiry_seconds": 60,
                "connect_timeout_seconds": 10,
                "retry_backoff_seconds": [1, 2, 5],
            },
        },
        "storage": {
            "sqlite_path": str(tmp_path / "state" / "outbox.db"),
            "retention_days": 7,
            "dead_letter_after_attempts": 20,
        },
        "observability": {
            "log_level": "INFO",
            "emit_health_events": True,
            "metrics_bind": "127.0.0.1:9108",
        },
    }
    bootstrap_path.parent.mkdir(parents=True, exist_ok=True)
    bootstrap_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return bootstrap_path
