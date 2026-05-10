from __future__ import annotations

import json

import paho.mqtt.client as mqtt
import pytest

from edge_telemetry_agent.application.delivery import PublishError
from edge_telemetry_agent.domain.config import MqttSettings
from edge_telemetry_agent.domain.events import MqttPublication
from edge_telemetry_agent.infrastructure import mqtt_publisher
from edge_telemetry_agent.infrastructure.mqtt_publisher import (
    PahoMqttPublisher,
    connect_mqtt_publisher,
    parse_mqtt_broker_uri,
)


class FakeMessageInfo:
    def __init__(self, *, published: bool = True, rc: int = mqtt.MQTT_ERR_SUCCESS) -> None:
        self._published = published
        self.rc = rc
        self.wait_timeout: float | None = None

    def wait_for_publish(self, *, timeout: float) -> None:
        self.wait_timeout = timeout

    def is_published(self) -> bool:
        return self._published


class FakePublishClient:
    def __init__(self, info: FakeMessageInfo | None = None) -> None:
        self.info = info or FakeMessageInfo()
        self.published: list[dict[str, object]] = []
        self.disconnected = False
        self.loop_stopped = False

    def publish(
        self,
        topic: str,
        payload: str,
        *,
        qos: int,
        retain: bool,
        properties: object,
    ) -> FakeMessageInfo:
        self.published.append(
            {
                "topic": topic,
                "payload": payload,
                "qos": qos,
                "retain": retain,
                "properties": properties,
            }
        )
        return self.info

    def disconnect(self) -> None:
        self.disconnected = True

    def loop_stop(self) -> None:
        self.loop_stopped = True


def _settings() -> MqttSettings:
    return MqttSettings(
        enabled=True,
        version="5.0",
        broker="mqtt://broker.local:1884",
        topic_root="idp/v1",
        client_id_prefix="edge-telemetry-agent",
        username_env="EDGE_AGENT_MQTT_USERNAME",
        password_env="EDGE_AGENT_MQTT_PASSWORD",
        qos=1,
        clean_start=True,
        session_expiry_seconds=0,
        telemetry_message_expiry_seconds=86400,
        connect_timeout_seconds=5,
        retry_backoff_seconds=(5, 15, 60),
    )


def test_parse_mqtt_broker_uri_supports_plain_and_tls_defaults() -> None:
    assert parse_mqtt_broker_uri("mqtt://broker.local") == mqtt_publisher.MqttBrokerEndpoint(
        host="broker.local",
        port=1883,
        use_tls=False,
    )
    assert parse_mqtt_broker_uri("mqtts://broker.local") == mqtt_publisher.MqttBrokerEndpoint(
        host="broker.local",
        port=8883,
        use_tls=True,
    )
    assert parse_mqtt_broker_uri("tcp://127.0.0.1:1884").port == 1884


def test_parse_mqtt_broker_uri_rejects_invalid_uri() -> None:
    with pytest.raises(ValueError, match="scheme"):
        parse_mqtt_broker_uri("http://broker.local")
    with pytest.raises(ValueError, match="host"):
        parse_mqtt_broker_uri("mqtt:///missing-host")


def test_paho_mqtt_publisher_publishes_json_with_mqtt5_properties() -> None:
    client = FakePublishClient()
    publisher = PahoMqttPublisher(client, publish_timeout_seconds=3.0)

    publisher.publish(
        MqttPublication(
            topic="idp/v1/assets/demo/agents/agent-1/sources/knx/points/2%2F0%2F0/event",
            payload={"message_type": "idp.edge.telemetry.event.v1", "value": 24.2},
            qos=1,
            retain=False,
            message_expiry_seconds=60,
        )
    )

    publication = client.published[0]
    assert publication["topic"] == (
        "idp/v1/assets/demo/agents/agent-1/sources/knx/points/2%2F0%2F0/event"
    )
    assert json.loads(str(publication["payload"])) == {
        "message_type": "idp.edge.telemetry.event.v1",
        "value": 24.2,
    }
    assert publication["qos"] == 1
    assert publication["retain"] is False
    properties = publication["properties"]
    assert properties.ContentType == "application/json"
    assert properties.MessageExpiryInterval == 60
    assert client.info.wait_timeout == 3.0


def test_paho_mqtt_publisher_raises_when_publish_does_not_complete() -> None:
    publisher = PahoMqttPublisher(FakePublishClient(FakeMessageInfo(published=False)))

    with pytest.raises(PublishError, match="did not complete"):
        publisher.publish(
            MqttPublication(
                topic="idp/v1/test",
                payload={"message_type": "idp.edge.telemetry.event.v1"},
                qos=1,
                retain=False,
            )
        )


def test_paho_mqtt_publisher_raises_when_publish_rc_fails() -> None:
    publisher = PahoMqttPublisher(FakePublishClient(FakeMessageInfo(rc=4)))

    with pytest.raises(PublishError, match="failed with rc=4"):
        publisher.publish(
            MqttPublication(
                topic="idp/v1/test",
                payload={"message_type": "idp.edge.telemetry.event.v1"},
                qos=1,
                retain=False,
            )
        )


def test_connect_mqtt_publisher_builds_authenticated_mqtt5_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clients: list[FakeConnectClient] = []

    class FakeConnectClient:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs
            self.username: str | None = None
            self.password: str | None = None
            self.connected: dict[str, object] | None = None
            self.loop_started = False
            self.tls_enabled = False
            clients.append(self)

        def tls_set(self) -> None:
            self.tls_enabled = True

        def username_pw_set(self, username: str, password: str | None = None) -> None:
            self.username = username
            self.password = password

        def connect(self, host: str, port: int, **kwargs: object) -> int:
            self.connected = {"host": host, "port": port, **kwargs}
            return mqtt.MQTT_ERR_SUCCESS

        def loop_start(self) -> None:
            self.loop_started = True

    monkeypatch.setattr(mqtt_publisher.mqtt, "Client", FakeConnectClient)
    monkeypatch.setenv("EDGE_AGENT_MQTT_USERNAME", "user-1")
    monkeypatch.setenv("EDGE_AGENT_MQTT_PASSWORD", "pass-1")

    publisher = connect_mqtt_publisher(_settings(), agent_id="agent-1")

    assert isinstance(publisher, PahoMqttPublisher)
    assert len(clients) == 1
    client = clients[0]
    assert client.kwargs["client_id"] == "edge-telemetry-agent-agent-1"
    assert client.kwargs["protocol"] == mqtt.MQTTv5
    assert client.username == "user-1"
    assert client.password == "pass-1"
    assert client.connected is not None
    assert client.connected["host"] == "broker.local"
    assert client.connected["port"] == 1884
    assert client.connected["clean_start"] is True
    assert client.connected["properties"].SessionExpiryInterval == 0
    assert client.loop_started is True


def test_connect_mqtt_publisher_fails_when_configured_credentials_are_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("EDGE_AGENT_MQTT_USERNAME", raising=False)

    with pytest.raises(PublishError, match="EDGE_AGENT_MQTT_USERNAME"):
        connect_mqtt_publisher(_settings(), agent_id="agent-1")


def test_connect_mqtt_publisher_rejects_non_mqtt5_settings() -> None:
    settings = _settings().model_copy(update={"version": "3.1.1"})

    with pytest.raises(PublishError, match="Unsupported MQTT version"):
        connect_mqtt_publisher(settings, agent_id="agent-1")
