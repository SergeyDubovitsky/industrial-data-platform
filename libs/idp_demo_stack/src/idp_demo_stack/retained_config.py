from __future__ import annotations

import contextlib
import json
import threading
from collections.abc import Callable

import paho.mqtt.client as mqtt

from idp_demo_stack.models import DemoSettings

Output = Callable[[str], None]


def wait_for_retained_config_projection(
    settings: DemoSettings,
    *,
    timeout_seconds: float,
    output: Output = print,
) -> None:
    if timeout_seconds <= 0:
        return

    expected_topics = {
        settings.scope.agent_runtime_config_topic(),
        *[
            settings.scope.source_config_topic(source.source_id)
            for source in settings.bundle.sources
        ],
    }
    received_topics: set[str] = set()
    ready = threading.Event()
    last_error = "retained config projection has not arrived yet"

    def on_connect(
        client: mqtt.Client,
        _userdata: object,
        _flags: mqtt.ConnectFlags,
        reason_code: mqtt.ReasonCode,
        _properties: mqtt.Properties | None,
    ) -> None:
        nonlocal last_error
        if reason_code.is_failure:
            last_error = f"connect reason_code={reason_code}"
            ready.set()
            return
        for topic in sorted(expected_topics):
            client.subscribe(topic, qos=1)

    def on_message(
        _client: mqtt.Client,
        _userdata: object,
        message: mqtt.MQTTMessage,
    ) -> None:
        nonlocal last_error
        try:
            payload = json.loads(message.payload.decode())
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            return
        if not isinstance(payload, dict):
            last_error = f"non-object payload on {message.topic}"
            return
        if message.topic in expected_topics:
            received_topics.add(message.topic)
        if received_topics == expected_topics:
            ready.set()

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"{settings.client_id}-config-waiter",
        protocol=mqtt.MQTTv5,
    )
    if settings.username:
        client.username_pw_set(settings.username, password=settings.password)
    client.on_connect = on_connect
    client.on_message = on_message
    try:
        client.connect(settings.broker.host, settings.broker.port, keepalive=20)
        client.loop_start()
        if not ready.wait(timeout_seconds):
            missing = sorted(expected_topics - received_topics)
            raise RuntimeError(
                "Timed out waiting for retained config projection. "
                f"missing_topics={missing} last_error={last_error}"
            )
        output(
            "RETAINED_CONFIG_READY "
            f"topics={len(received_topics)} agent_id={settings.bundle.agent_id}"
        )
    finally:
        with contextlib.suppress(Exception):
            client.disconnect()
        client.loop_stop()
