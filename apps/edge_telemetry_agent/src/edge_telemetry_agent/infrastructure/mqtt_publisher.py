from __future__ import annotations

import contextlib
import json
import os
from dataclasses import dataclass
from urllib.parse import urlparse

import paho.mqtt.client as mqtt
from paho.mqtt.packettypes import PacketTypes
from paho.mqtt.properties import Properties

from edge_telemetry_agent.application.delivery import PublishError
from edge_telemetry_agent.domain.config import MqttSettings
from edge_telemetry_agent.domain.events import MqttPublication


@dataclass(frozen=True)
class MqttBrokerEndpoint:
    """Parsed MQTT broker endpoint used by the Paho adapter."""

    host: str
    port: int
    use_tls: bool = False


class PahoMqttPublisher:
    """Concrete `PublicationPublisher` implementation backed by paho-mqtt."""

    def __init__(
        self,
        client: mqtt.Client,
        *,
        publish_timeout_seconds: float = 10.0,
    ) -> None:
        """Wrap an already connected Paho client for MQTT publication calls."""
        self._client = client
        self._publish_timeout_seconds = publish_timeout_seconds

    def publish(self, publication: MqttPublication) -> None:
        """Publish JSON payload with MQTT v5 content type and optional expiry."""
        payload_json = json.dumps(
            publication.payload,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        properties = Properties(PacketTypes.PUBLISH)
        properties.ContentType = "application/json"
        if publication.message_expiry_seconds is not None:
            properties.MessageExpiryInterval = publication.message_expiry_seconds

        message_info = self._client.publish(
            publication.topic,
            payload_json,
            qos=publication.qos,
            retain=publication.retain,
            properties=properties,
        )
        message_info.wait_for_publish(timeout=self._publish_timeout_seconds)
        if not message_info.is_published():
            raise PublishError(
                f"MQTT publication to {publication.topic!r} did not complete "
                f"within {self._publish_timeout_seconds:g} seconds"
            )
        if message_info.rc != mqtt.MQTT_ERR_SUCCESS:
            raise PublishError(
                f"MQTT publication to {publication.topic!r} failed with rc={message_info.rc}"
            )

    def close(self) -> None:
        """Disconnect the underlying MQTT client and stop its network loop."""
        with contextlib.suppress(Exception):
            self._client.disconnect()
        self._client.loop_stop()


def connect_mqtt_publisher(
    settings: MqttSettings,
    *,
    agent_id: str,
) -> PahoMqttPublisher:
    """Create, authenticate, connect, and start a Paho MQTT v5 publisher."""
    if settings.version != "5.0":
        raise PublishError(f"Unsupported MQTT version {settings.version!r}; expected '5.0'")
    endpoint = parse_mqtt_broker_uri(settings.broker)
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"{settings.client_id_prefix}-{agent_id}",
        protocol=mqtt.MQTTv5,
    )
    if endpoint.use_tls:
        client.tls_set()

    username = _env_value(settings.username_env, kind="username")
    password = _env_value(settings.password_env, kind="password")
    if username is not None:
        client.username_pw_set(username, password=password)

    connect_properties = Properties(PacketTypes.CONNECT)
    connect_properties.SessionExpiryInterval = settings.session_expiry_seconds
    rc = client.connect(
        endpoint.host,
        endpoint.port,
        keepalive=20,
        clean_start=settings.clean_start,
        properties=connect_properties,
    )
    if rc != mqtt.MQTT_ERR_SUCCESS:
        raise PublishError(
            f"MQTT broker {endpoint.host}:{endpoint.port} rejected connection with rc={rc}"
        )
    client.loop_start()
    return PahoMqttPublisher(client)


def parse_mqtt_broker_uri(value: str) -> MqttBrokerEndpoint:
    """Parse configured broker URI into host, port, and TLS mode."""
    parsed = urlparse(value)
    if parsed.scheme not in {"mqtt", "tcp", "mqtts", "ssl"}:
        raise ValueError(
            "MQTT broker URI must use mqtt://, tcp://, mqtts://, or ssl:// scheme"
        )
    if not parsed.hostname:
        raise ValueError("MQTT broker URI must include host")
    use_tls = parsed.scheme in {"mqtts", "ssl"}
    return MqttBrokerEndpoint(
        host=parsed.hostname,
        port=parsed.port or (8883 if use_tls else 1883),
        use_tls=use_tls,
    )


def _env_value(env_name: str | None, *, kind: str) -> str | None:
    if env_name is None:
        return None
    value = os.getenv(env_name)
    if value is None:
        raise PublishError(f"MQTT {kind} environment variable {env_name!r} is not set")
    return value
