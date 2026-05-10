from __future__ import annotations

import json
from collections.abc import Callable
from typing import Protocol

import paho.mqtt.client as mqtt

from idp_demo_stack.models import DemoSettings, PublishMessage

Output = Callable[[str], None]


class JsonPublisher(Protocol):
    def publish(self, message: PublishMessage) -> None: ...

    def close(self) -> None: ...


class PahoJsonPublisher:
    def __init__(self, client: mqtt.Client, *, output: Output = print) -> None:
        self._client = client
        self._output = output

    def publish(self, message: PublishMessage) -> None:
        payload_json = json.dumps(
            message.payload,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        publish_info = self._client.publish(
            message.topic,
            payload_json,
            qos=message.qos,
            retain=message.retain,
        )
        publish_info.wait_for_publish(timeout=10)
        if not publish_info.is_published():
            raise RuntimeError(f"Publish timed out for topic {message.topic}")
        if publish_info.rc != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError(
                f"Publish failed for topic {message.topic} with rc={publish_info.rc}"
            )
        self._output(
            "PUBLISHED "
            f"retain={message.retain} topic={message.topic} payload={payload_json}"
        )

    def close(self) -> None:
        self._client.disconnect()
        self._client.loop_stop()


def connect_publisher(
    *,
    settings: DemoSettings,
    output: Output = print,
) -> JsonPublisher:
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=settings.client_id,
        protocol=mqtt.MQTTv5,
    )
    if settings.username:
        client.username_pw_set(settings.username, password=settings.password)
    client.connect(settings.broker.host, settings.broker.port, keepalive=20)
    client.loop_start()
    return PahoJsonPublisher(client, output=output)
