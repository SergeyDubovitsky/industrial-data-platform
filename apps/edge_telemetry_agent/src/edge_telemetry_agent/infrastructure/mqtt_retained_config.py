from __future__ import annotations

import contextlib
import json
import os
import re
import threading
import time

import paho.mqtt.client as mqtt
from paho.mqtt.packettypes import PacketTypes
from paho.mqtt.properties import Properties

from edge_telemetry_agent.domain.config import ConfigurationError, MqttSettings
from edge_telemetry_agent.infrastructure.mqtt_publisher import parse_mqtt_broker_uri
from edge_telemetry_agent.modeling import FrozenEdgeModel


class RetainedConfigDocuments(FrozenEdgeModel):
    agent_runtime_config: dict[str, object]
    source_configs: dict[str, dict[str, object]]


class RetainedConfigLoader:
    def __init__(self, settings: MqttSettings, *, agent_id: str) -> None:
        self._settings = settings
        self._agent_id = agent_id

    def load(self) -> RetainedConfigDocuments:
        collector = _RetainedCollector(self._settings, agent_id=self._agent_id)
        return collector.collect()


class _RetainedCollector:
    def __init__(self, settings: MqttSettings, *, agent_id: str) -> None:
        self._settings = settings
        self._agent_id = agent_id
        self._condition = threading.Condition()
        self._agent_runtime_payload: dict[str, object] | None = None
        self._source_payloads: dict[str, dict[str, object]] = {}
        self._error: Exception | None = None
        self._source_topic_pattern = re.compile(
            rf"^{re.escape(settings.topic_root)}/agents/{re.escape(agent_id)}/sources/([^/]+)/config$"
        )

    def collect(self) -> RetainedConfigDocuments:
        endpoint = parse_mqtt_broker_uri(self._settings.broker)
        client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"{self._settings.client_id_prefix}-{self._agent_id}-config",
            protocol=mqtt.MQTTv5,
        )
        if endpoint.use_tls:
            client.tls_set()

        username = _env_value(self._settings.username_env, kind="username")
        password = _env_value(self._settings.password_env, kind="password")
        if username is not None:
            client.username_pw_set(username, password=password)

        client.on_connect = self._on_connect
        client.on_message = self._on_message
        client.on_disconnect = self._on_disconnect

        connect_properties = Properties(PacketTypes.CONNECT)
        connect_properties.SessionExpiryInterval = self._settings.session_expiry_seconds

        rc = client.connect(
            endpoint.host,
            endpoint.port,
            keepalive=20,
            clean_start=self._settings.clean_start,
            properties=connect_properties,
        )
        if rc != mqtt.MQTT_ERR_SUCCESS:
            raise ConfigurationError(
                "MQTT broker rejected retained config connection "
                f"{endpoint.host}:{endpoint.port} with rc={rc}"
            )

        client.loop_start()
        deadline = time.monotonic() + self._settings.connect_timeout_seconds
        try:
            with self._condition:
                while True:
                    if self._error is not None:
                        raise ConfigurationError(f"Failed to fetch retained config: {self._error}")
                    if self._is_complete():
                        return RetainedConfigDocuments(
                            agent_runtime_config=self._agent_runtime_payload or {},
                            source_configs=dict(self._source_payloads),
                        )
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise ConfigurationError(
                            "Timed out waiting for retained agent-runtime/source config "
                            f"for agent {self._agent_id}"
                        )
                    self._condition.wait(timeout=remaining)
        finally:
            with contextlib.suppress(Exception):
                client.disconnect()
            client.loop_stop()

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata: object,
        flags: dict[str, object],
        reason_code: mqtt.ReasonCode,
        properties: Properties | None,
    ) -> None:
        if reason_code.is_failure:
            with self._condition:
                self._error = RuntimeError(f"connect reason_code={reason_code}")
                self._condition.notify_all()
            return
        agent_runtime_topic = (
            f"{self._settings.topic_root}/agents/{self._agent_id}/config/agent-runtime"
        )
        source_topic = (
            f"{self._settings.topic_root}/agents/{self._agent_id}/sources/+/config"
        )
        client.subscribe(agent_runtime_topic, qos=self._settings.qos)
        client.subscribe(source_topic, qos=self._settings.qos)

    def _on_disconnect(
        self,
        client: mqtt.Client,
        userdata: object,
        flags: mqtt.DisconnectFlags,
        reason_code: mqtt.ReasonCode,
        properties: Properties | None,
    ) -> None:
        if not reason_code.is_failure:
            return
        with self._condition:
            if self._agent_runtime_payload is None:
                self._error = RuntimeError(f"disconnect reason_code={reason_code}")
                self._condition.notify_all()

    def _on_message(
        self,
        client: mqtt.Client,
        userdata: object,
        message: mqtt.MQTTMessage,
    ) -> None:
        try:
            payload = json.loads(message.payload.decode("utf-8"))
            if not isinstance(payload, dict):
                raise TypeError("retained config payload must be a JSON object")
        except Exception as exc:
            with self._condition:
                self._error = exc
                self._condition.notify_all()
            return

        topic = message.topic
        agent_runtime_topic = (
            f"{self._settings.topic_root}/agents/{self._agent_id}/config/agent-runtime"
        )
        with self._condition:
            if topic == agent_runtime_topic:
                self._agent_runtime_payload = payload
            else:
                match = self._source_topic_pattern.match(topic)
                if match is not None:
                    self._source_payloads[match.group(1)] = payload
            self._condition.notify_all()

    def _is_complete(self) -> bool:
        if self._agent_runtime_payload is None:
            return False
        for source_id in _required_source_ids(self._agent_runtime_payload):
            if source_id not in self._source_payloads:
                return False
        return True


def _required_source_ids(agent_runtime_payload: dict[str, object]) -> list[str]:
    sources = agent_runtime_payload.get("sources")
    if not isinstance(sources, list):
        return []
    required: list[str] = []
    for item in sources:
        if isinstance(item, dict):
            source_id = item.get("source_id")
            if isinstance(source_id, str) and source_id:
                required.append(source_id)
    return required


def _env_value(env_name: str | None, *, kind: str) -> str | None:
    if env_name is None:
        return None
    value = os.getenv(env_name)
    if value is None:
        raise ConfigurationError(f"MQTT {kind} environment variable {env_name!r} is not set")
    return value
