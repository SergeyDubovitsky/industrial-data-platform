from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from idp_demo_stack.models import (
    BundlePoint,
    BundleSource,
    DemoSettings,
    KafkaRecord,
    PublishMessage,
    WaveConfig,
)
from idp_demo_stack.publisher import JsonPublisher
from idp_demo_stack.runtime import RuntimePort

EDGE_CONFIG_TOPIC = "idp.edge.configs.v1"


def agent_runtime_config_payload(settings: DemoSettings) -> dict[str, Any]:
    return {
        "message_type": "idp.edge.agent-runtime-config.v1",
        "tenant_id": settings.bundle.tenant_id,
        "asset_id": settings.bundle.asset_id,
        "agent_id": settings.bundle.agent_id,
        "config_revision": settings.bundle.config_revision,
        "issued_at": settings.bundle.issued_at,
        "sources": [
            {
                "source_id": source.source_id,
                "source_config_revision": source.source_config_revision,
                "enabled": source.enabled,
            }
            for source in settings.bundle.sources
        ],
    }


def source_config_payload(
    settings: DemoSettings,
    *,
    source: BundleSource,
) -> dict[str, Any]:
    return {
        "message_type": "idp.edge.source-config.v1",
        "tenant_id": settings.bundle.tenant_id,
        "asset_id": settings.bundle.asset_id,
        "agent_id": settings.bundle.agent_id,
        "config_revision": settings.bundle.config_revision,
        "source_id": source.source_id,
        "source_config_revision": source.source_config_revision,
        "source_type": source.source_type,
        "enabled": source.enabled,
        "connection": dict(source.connection),
        "acquisition_defaults": dict(source.acquisition_defaults),
        "publish_defaults": dict(source.publish_defaults),
        "points": [point.source_config_entry() for point in source.points],
    }


def config_delivery_records(settings: DemoSettings) -> list[KafkaRecord]:
    agent_runtime_payload = agent_runtime_config_payload(settings)
    records = [
        KafkaRecord(
            topic=EDGE_CONFIG_TOPIC,
            key=(
                f"{settings.bundle.tenant_id}|{settings.bundle.asset_id}|"
                f"{settings.bundle.agent_id}|agent_runtime"
            ),
            payload=_config_delivery_record(
                settings=settings,
                config_scope="agent_runtime",
                source_id=None,
                source_config_revision=None,
                target_mqtt_topic=settings.scope.agent_runtime_config_topic(),
                payload_message_type="idp.edge.agent-runtime-config.v1",
                payload=agent_runtime_payload,
            ),
        )
    ]
    for source in settings.bundle.sources:
        config_scope = f"source:{source.source_id}"
        records.append(
            KafkaRecord(
                topic=EDGE_CONFIG_TOPIC,
                key=(
                    f"{settings.bundle.tenant_id}|{settings.bundle.asset_id}|"
                    f"{settings.bundle.agent_id}|{config_scope}"
                ),
                payload=_config_delivery_record(
                    settings=settings,
                    config_scope=config_scope,
                    source_id=source.source_id,
                    source_config_revision=source.source_config_revision,
                    target_mqtt_topic=settings.scope.source_config_topic(
                        source.source_id
                    ),
                    payload_message_type="idp.edge.source-config.v1",
                    payload=source_config_payload(settings, source=source),
                ),
            )
        )
    return records


def _config_delivery_record(
    *,
    settings: DemoSettings,
    config_scope: str,
    source_id: str | None,
    source_config_revision: str | None,
    target_mqtt_topic: str,
    payload_message_type: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    idempotency_scope = config_scope.replace(":", "|")
    return {
        "message_type": "idp.edge.config.delivery.v1",
        "tenant_id": settings.bundle.tenant_id,
        "asset_id": settings.bundle.asset_id,
        "agent_id": settings.bundle.agent_id,
        "config_revision": settings.bundle.config_revision,
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
            f"{settings.bundle.tenant_id}|{settings.bundle.asset_id}|"
            f"{settings.bundle.agent_id}|{settings.bundle.config_revision}|"
            f"{idempotency_scope}"
        ),
        "issued_at": settings.bundle.issued_at,
    }


def telemetry_payload(
    *,
    settings: DemoSettings,
    source: BundleSource,
    point: BundlePoint,
    event_id: str,
    sequence: int,
    value: bool | float,
    value_raw: str,
    ts: str,
) -> dict[str, Any]:
    return {
        "message_type": "idp.edge.telemetry.event.v1",
        "tenant_id": settings.bundle.tenant_id,
        "event_id": event_id,
        "event_type": (
            "telemetry.changed"
            if point.value_type == "boolean"
            else "telemetry.sample"
        ),
        "source_config_revision": source.source_config_revision,
        "ts": ts,
        "observation_mode": "listen",
        "value": value,
        "value_raw": value_raw,
        "quality": "good",
        "sequence": sequence,
    }


def connection_payload(
    state: str,
    *,
    tenant_id: str,
    ts: str,
    reason: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "message_type": "idp.edge.source.connection.v1",
        "tenant_id": tenant_id,
        "state": state,
        "ts": ts,
    }
    if reason is not None:
        payload["reason"] = reason
    return payload


def lwt_payload(status: str, *, tenant_id: str, ts: str) -> dict[str, Any]:
    return {
        "message_type": "idp.edge.agent.lwt.v1",
        "tenant_id": tenant_id,
        "status": status,
        "ts": ts,
    }


@dataclass
class DemoScenario:
    settings: DemoSettings
    runtime: RuntimePort

    def config_messages(self) -> list[PublishMessage]:
        messages: list[PublishMessage] = []
        if self.settings.publish_config:
            messages.append(
                PublishMessage(
                    topic=self.settings.scope.agent_runtime_config_topic(),
                    payload=agent_runtime_config_payload(self.settings),
                    retain=True,
                )
            )
            for source in self.settings.bundle.sources:
                messages.append(
                    PublishMessage(
                        topic=self.settings.scope.source_config_topic(source.source_id),
                        payload=source_config_payload(self.settings, source=source),
                        retain=True,
                    )
                )
        return messages

    def bootstrap_messages(self) -> list[PublishMessage]:
        ts = self.runtime.now_utc_iso()
        messages = self.config_messages()

        if self.settings.publish_status:
            messages.extend(
                (
                    PublishMessage(
                        topic=self.settings.scope.source_status_topic(
                            self.settings.telemetry_source_id
                        ),
                        payload=connection_payload(
                            "connected",
                            tenant_id=self.settings.bundle.tenant_id,
                            ts=ts,
                        ),
                        retain=True,
                    ),
                    PublishMessage(
                        topic=self.settings.scope.agent_lwt_topic(),
                        payload=lwt_payload(
                            "online",
                            tenant_id=self.settings.bundle.tenant_id,
                            ts=ts,
                        ),
                        retain=True,
                    ),
                )
            )

        return messages

    def cycle_messages(
        self,
        *,
        cycle: int,
        sequence: dict[str, int],
    ) -> list[PublishMessage]:
        source = self.settings.bundle.source(self.settings.telemetry_source_id)
        messages: list[PublishMessage] = []

        numeric_point = _first_numeric_point(source)
        if numeric_point is not None:
            temperature = temperature_value(cycle, wave=self.settings.temperature)
            sequence[numeric_point.point_ref] += 1
            messages.append(
                PublishMessage(
                    topic=self.settings.scope.point_topic(
                        source.source_id,
                        numeric_point.point_key,
                        "event",
                    ),
                    payload=telemetry_payload(
                        settings=self.settings,
                        source=source,
                        point=numeric_point,
                        event_id=f"manual-numeric-{cycle:06d}",
                        sequence=sequence[numeric_point.point_ref],
                        value=temperature,
                        value_raw=f"{temperature:.1f}",
                        ts=self.runtime.now_utc_iso(),
                    ),
                )
            )

        boolean_point = _first_boolean_point(source)
        if boolean_point is not None:
            switch_on = cycle % 2 == 1
            sequence[boolean_point.point_ref] += 1
            messages.append(
                PublishMessage(
                    topic=self.settings.scope.point_topic(
                        source.source_id,
                        boolean_point.point_key,
                        "event",
                    ),
                    payload=telemetry_payload(
                        settings=self.settings,
                        source=source,
                        point=boolean_point,
                        event_id=f"manual-boolean-{cycle:06d}",
                        sequence=sequence[boolean_point.point_ref],
                        value=switch_on,
                        value_raw="01" if switch_on else "00",
                        ts=self.runtime.now_utc_iso(),
                    ),
                )
            )

        return messages

    def shutdown_messages(self, *, reason: str) -> list[PublishMessage]:
        if not self.settings.publish_status:
            return []

        ts = self.runtime.now_utc_iso()
        return [
            PublishMessage(
                topic=self.settings.scope.source_status_topic(self.settings.telemetry_source_id),
                payload=connection_payload(
                    "disconnected",
                    tenant_id=self.settings.bundle.tenant_id,
                    ts=ts,
                    reason=reason,
                ),
                retain=True,
            ),
            PublishMessage(
                topic=self.settings.scope.agent_lwt_topic(),
                payload=lwt_payload(
                    "offline",
                    tenant_id=self.settings.bundle.tenant_id,
                    ts=ts,
                ),
                retain=True,
            ),
        ]


def publish_messages(
    publisher: JsonPublisher,
    messages: Iterable[PublishMessage],
) -> None:
    for message in messages:
        publisher.publish(message)


def temperature_value(cycle: int, *, wave: WaveConfig) -> float:
    if wave.period <= 0:
        return round(wave.base, 1)
    phase = (cycle / wave.period) * (2 * math.pi)
    return round(wave.base + wave.amplitude * math.sin(phase), 1)


def run_demo(
    settings: DemoSettings,
    *,
    publisher: JsonPublisher,
    runtime: RuntimePort,
    output: callable = print,
) -> int:
    scenario = DemoScenario(settings=settings, runtime=runtime)
    source = settings.bundle.source(settings.telemetry_source_id)
    sequence = {point.point_ref: 0 for point in source.points}

    try:
        publish_messages(publisher, scenario.bootstrap_messages())
        next_bootstrap_refresh: float | None = None
        if settings.retained_refresh_seconds > 0:
            next_bootstrap_refresh = runtime.monotonic() + settings.retained_refresh_seconds

        cycle = 0
        while settings.count == 0 or cycle < settings.count:
            current_time = runtime.monotonic()
            if next_bootstrap_refresh is not None and current_time >= next_bootstrap_refresh:
                publish_messages(publisher, scenario.bootstrap_messages())
                next_bootstrap_refresh = current_time + settings.retained_refresh_seconds

            cycle += 1
            publish_messages(
                publisher,
                scenario.cycle_messages(cycle=cycle, sequence=sequence),
            )

            if settings.count == 0 or cycle < settings.count:
                runtime.sleep(settings.interval_seconds)
    except KeyboardInterrupt:
        output("STOP requested by user, publishing offline status.")
    finally:
        try:
            publish_messages(
                publisher,
                scenario.shutdown_messages(reason="manual-stop"),
            )
        except Exception as exc:  # pragma: no cover
            output(f"WARNING failed to publish shutdown status: {exc}")

    return 0


def publish_config(
    settings: DemoSettings,
    *,
    publisher: JsonPublisher,
    runtime: RuntimePort,
    output: callable = print,
) -> int:
    scenario = DemoScenario(settings=settings, runtime=runtime)
    messages = scenario.config_messages()
    publish_messages(publisher, messages)
    output(
        "PUBLISHED_CONFIG "
        f"messages={len(messages)} "
        f"sources={len(settings.bundle.sources)} "
        f"agent_id={settings.bundle.agent_id}"
    )
    return len(messages)


def _first_numeric_point(source: BundleSource) -> BundlePoint | None:
    for point in source.points:
        if point.value_type == "number" and point.publish.get("enabled", True):
            return point
    return None


def _first_boolean_point(source: BundleSource) -> BundlePoint | None:
    for point in source.points:
        if (
            point.value_type == "boolean"
            and point.signal_type != "command"
            and point.publish.get("enabled", True)
        ):
            return point
    return None
