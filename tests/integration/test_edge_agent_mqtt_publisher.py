from __future__ import annotations

import json
import threading
from pathlib import Path
from uuid import uuid4

import paho.mqtt.client as mqtt
import pytest
import yaml

from edge_telemetry_agent.cli import main
from edge_telemetry_agent.domain.config import MqttSettings
from edge_telemetry_agent.domain.events import MqttPublication
from edge_telemetry_agent.infrastructure.mqtt_publisher import connect_mqtt_publisher
from idp_demo_stack.bundle import load_bundle
from idp_demo_stack.models import TopicScope
from idp_demo_stack.scenario import agent_runtime_config_payload, source_config_payload

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_BUNDLE_PATH = REPO_ROOT / "environments" / "demo-stand" / "edge_telemetry_agent" / "config.bundle.yaml"


@pytest.mark.integration_smoke
def test_edge_agent_mqtt_publisher_sends_publication_to_local_broker(
    local_stack,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    topic = f"idp/v1/edge-telemetry-agent-smoke/{uuid4().hex}"
    connected = threading.Event()
    received = threading.Event()
    subscribed = threading.Event()
    received_payloads: list[dict[str, object]] = []

    subscriber = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    subscriber.username_pw_set(local_stack.mqtt_username, local_stack.mqtt_password)

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
    subscriber.connect("127.0.0.1", local_stack.mqtt_port, keepalive=20)
    subscriber.loop_start()
    assert connected.wait(timeout=10), "MQTT subscriber did not connect in time"
    subscriber.subscribe(topic, qos=1)
    assert subscribed.wait(timeout=10), "MQTT subscriber did not subscribe in time"

    monkeypatch.setenv("EDGE_AGENT_MQTT_USERNAME", local_stack.mqtt_username)
    monkeypatch.setenv("EDGE_AGENT_MQTT_PASSWORD", local_stack.mqtt_password)
    publisher = connect_mqtt_publisher(
        MqttSettings(
            enabled=True,
            version="5.0",
            broker=f"mqtt://127.0.0.1:{local_stack.mqtt_port}",
            topic_root="idp/v1",
            client_id_prefix="edge-telemetry-agent-it",
            username_env="EDGE_AGENT_MQTT_USERNAME",
            password_env="EDGE_AGENT_MQTT_PASSWORD",
            qos=1,
            clean_start=True,
            session_expiry_seconds=0,
            telemetry_message_expiry_seconds=60,
            connect_timeout_seconds=10,
            retry_backoff_seconds=(1, 2, 5),
        ),
        agent_id=f"agent-{uuid4().hex[:8]}",
    )

    try:
        publisher.publish(
            MqttPublication(
                topic=topic,
                payload={
                    "message_type": "idp.edge.telemetry.event.v1",
                    "tenant_id": "tenant-it",
                    "event_id": f"smoke-{uuid4().hex}",
                    "event_type": "telemetry.sample",
                    "source_config_revision": "rev-it-001",
                    "ts": "2026-05-02T12:00:00Z",
                    "observation_mode": "listen",
                    "value": 24.2,
                    "value_raw": "24.2",
                    "quality": "good",
                    "sequence": 1,
                },
                qos=1,
                retain=False,
                message_expiry_seconds=60,
            )
        )
        assert received.wait(timeout=10), "MQTT subscriber did not receive edge publication"
        assert received_payloads[0]["message_type"] == "idp.edge.telemetry.event.v1"
        assert received_payloads[0]["tenant_id"] == "tenant-it"
        assert received_payloads[0]["source_config_revision"] == "rev-it-001"
        assert received_payloads[0]["value"] == 24.2
    finally:
        publisher.close()
        subscriber.disconnect()
        subscriber.loop_stop()


def test_edge_agent_deliver_once_sends_sqlite_outbox_event_to_local_broker(
    local_stack,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle = _load_demo_bundle(monkeypatch)
    bootstrap_path = _write_bootstrap_config(
        tmp_path,
        agent_id=bundle.agent_id,
        broker=f"mqtt://127.0.0.1:{local_stack.mqtt_port}",
    )
    _seed_retained_config(local_stack=local_stack, bundle=bundle)

    point = bundle.source("knx_main").points[1]
    topic = (
        f"idp/v1/assets/{bundle.asset_id}/agents/{bundle.agent_id}"
        f"/sources/knx_main/points/{point.point_key}/event"
    )
    connected = threading.Event()
    received = threading.Event()
    subscribed = threading.Event()
    received_payloads: list[dict[str, object]] = []
    subscriber = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    subscriber.username_pw_set(local_stack.mqtt_username, local_stack.mqtt_password)

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
    subscriber.connect("127.0.0.1", local_stack.mqtt_port, keepalive=20)
    subscriber.loop_start()
    assert connected.wait(timeout=10), "MQTT subscriber did not connect in time"
    subscriber.subscribe(topic, qos=1)
    assert subscribed.wait(timeout=10), "MQTT subscriber did not subscribe in time"

    monkeypatch.setenv("MQTT_USERNAME", local_stack.mqtt_username)
    monkeypatch.setenv("MQTT_PASSWORD", local_stack.mqtt_password)

    try:
        enqueue_exit = main(
            [
                "enqueue-demo-event",
                "--bootstrap-config",
                str(bootstrap_path),
                "--source-id",
                "knx_main",
                "--point-ref",
                point.point_ref,
                "--value",
                "1",
            ]
        )
        assert enqueue_exit == 0
        capsys.readouterr()

        deliver_exit = main(
            [
                "deliver-once",
                "--bootstrap-config",
                str(bootstrap_path),
            ]
        )

        captured = capsys.readouterr()
        assert deliver_exit == 0
        assert "Delivery run: reserved=1 published=1 retry=0 dead_letter=0" in captured.out
        assert received.wait(timeout=10), "MQTT subscriber did not receive outbox event"
        assert received_payloads[0]["message_type"] == "idp.edge.telemetry.event.v1"
        assert received_payloads[0]["tenant_id"] == bundle.tenant_id
        assert received_payloads[0]["source_config_revision"] == "rev-demo-stand-knx-main-001"
        assert received_payloads[0]["value"] is True
    finally:
        subscriber.disconnect()
        subscriber.loop_stop()


def _load_demo_bundle(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("KNX_LOCAL_GATEWAY_IP", "127.0.0.1")
    monkeypatch.setenv("KNX_LOCAL_GATEWAY_PORT", "3671")
    monkeypatch.setenv("KNX_LOCAL_ROUTE_BACK", "false")
    return load_bundle(DEMO_BUNDLE_PATH)


def _seed_retained_config(*, local_stack, bundle) -> None:
    settings = type("BundleSettings", (), {"bundle": bundle})()
    scope = TopicScope(
        topic_root="idp/v1",
        asset_id=bundle.asset_id,
        agent_id=bundle.agent_id,
    )
    publish_json_message(
        host="127.0.0.1",
        port=local_stack.mqtt_port,
        username=local_stack.mqtt_username,
        password=local_stack.mqtt_password,
        topic=scope.agent_runtime_config_topic(),
        payload=agent_runtime_config_payload(settings),
        retain=True,
    )
    for source in bundle.sources:
        publish_json_message(
            host="127.0.0.1",
            port=local_stack.mqtt_port,
            username=local_stack.mqtt_username,
            password=local_stack.mqtt_password,
            topic=scope.source_config_topic(source.source_id),
            payload=source_config_payload(settings, source=source),
            retain=True,
        )


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
