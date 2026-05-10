from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from idp_demo_stack.cli import settings_from_args
from idp_demo_stack.models import DemoSettings
from idp_demo_stack.scenario import DemoScenario, config_delivery_records, run_demo


class FakeRuntime:
    def __init__(self) -> None:
        self.current = 0.0
        self.now_index = 0
        self.sleep_calls: list[float] = []

    def now_utc_iso(self) -> str:
        self.now_index += 1
        return f"2026-03-29T11:00:{self.now_index:02d}Z"

    def monotonic(self) -> float:
        return self.current

    def sleep(self, seconds: float) -> None:
        self.sleep_calls.append(seconds)
        self.current += seconds


class FakePublisher:
    def __init__(self) -> None:
        self.messages: list[object] = []

    def publish(self, message: object) -> None:
        self.messages.append(message)

    def close(self) -> None:
        return None


def _write_bundle(tmp_path: Path) -> Path:
    bundle_path = tmp_path / "config.bundle.yaml"
    bundle_path.write_text(
        """
tenant_id: tenant-001
asset_id: demo-stand-01
agent_id: manual-edge-demo
config_revision: rev-2026-05-02-001
issued_at: "2026-05-02T00:00:00Z"
sources:
  - source_id: knx_main
    source_config_revision: rev-2026-05-02-001-knx-main
    source_type: knx
    enabled: true
    connection:
      gateway_ip: 127.0.0.1
      gateway_port: 3671
    acquisition_defaults:
      listen: true
      read_on_start: false
      periodic_interval_seconds: null
    publish_defaults:
      enabled: true
      change_threshold: null
    points:
      - point_key: 2%2F0%2F0
        point_ref: 2/0/0
        name: temperature
        description: null
        signal_type: sensor
        value_type: number
        value_model: knx.dpt.9.001
        unit: C
        acquisition:
          listen: true
          read_on_start: true
          periodic_interval_seconds: null
        publish:
          enabled: true
          change_threshold: 1.0
        tags:
          room: demo
      - point_key: 0%2F0%2F7
        point_ref: 0/0/7
        name: switch_feedback
        description: null
        signal_type: feedback
        value_type: boolean
        value_model: knx.dpt.1.001
        unit: null
        acquisition:
          listen: true
          read_on_start: false
          periodic_interval_seconds: null
        publish:
          enabled: true
          change_threshold: null
        tags:
          room: demo
""".strip(),
        encoding="utf-8",
    )
    return bundle_path


def make_settings(tmp_path: Path, **overrides: object) -> DemoSettings:
    class Args:
        bundle_config = _write_bundle(tmp_path)
        broker = "mqtt://localhost:1883"
        kafka_bootstrap_servers = "localhost:19092"
        kafka_client_id = "demo-kafka-client"
        config_registry_url = "http://localhost:8000"
        config_delivery = "mqtt"
        config_projection_timeout_seconds = 15.0
        username = "demo-user"
        password = "demo-pass"
        topic_root = "idp/v1"
        source_id = None
        client_id = "demo-client"
        interval_seconds = 2.0
        count = 2
        temperature_base = 23.0
        temperature_amplitude = 1.8
        temperature_period = 8.0
        no_config = False
        no_status = False
        retained_refresh_seconds = 30.0

    settings = settings_from_args(Args())
    return replace(settings, **overrides)


def test_bootstrap_messages_are_derived_from_bundle(tmp_path: Path) -> None:
    scenario = DemoScenario(
        settings=make_settings(tmp_path),
        runtime=FakeRuntime(),
    )

    messages = scenario.bootstrap_messages()

    assert [message.topic for message in messages] == [
        scenario.settings.scope.agent_runtime_config_topic(),
        scenario.settings.scope.source_config_topic("knx_main"),
        scenario.settings.scope.source_status_topic("knx_main"),
        scenario.settings.scope.agent_lwt_topic(),
    ]
    assert all(message.retain for message in messages)
    assert messages[0].payload["message_type"] == "idp.edge.agent-runtime-config.v1"
    assert messages[1].payload["message_type"] == "idp.edge.source-config.v1"
    assert messages[2].payload["tenant_id"] == "tenant-001"
    assert messages[2].payload["state"] == "connected"
    assert messages[3].payload["tenant_id"] == "tenant-001"
    assert messages[3].payload["status"] == "online"


def test_run_demo_republishes_retained_messages_on_schedule(tmp_path: Path) -> None:
    runtime = FakeRuntime()
    publisher = FakePublisher()
    settings = make_settings(tmp_path, retained_refresh_seconds=1.0, count=2)

    result = run_demo(
        settings,
        publisher=publisher,
        runtime=runtime,
        output=lambda _: None,
    )

    topics = [message.topic for message in publisher.messages]

    assert result == 0
    assert topics.count(settings.scope.agent_runtime_config_topic()) == 2
    assert topics.count(settings.scope.source_config_topic("knx_main")) == 2
    assert topics.count(settings.scope.source_status_topic("knx_main")) == 3
    assert topics.count(settings.scope.agent_lwt_topic()) == 3
    assert runtime.sleep_calls == [2.0]
    assert publisher.messages[-2].payload["tenant_id"] == "tenant-001"
    assert publisher.messages[-2].payload["state"] == "disconnected"
    assert publisher.messages[-1].payload["tenant_id"] == "tenant-001"
    assert publisher.messages[-1].payload["status"] == "offline"


def test_cycle_messages_publish_tenant_and_source_config_revision(tmp_path: Path) -> None:
    scenario = DemoScenario(
        settings=make_settings(tmp_path),
        runtime=FakeRuntime(),
    )

    messages = scenario.cycle_messages(
        cycle=1,
        sequence={"2/0/0": 0, "0/0/7": 0},
    )

    assert len(messages) == 2
    assert messages[0].payload["tenant_id"] == "tenant-001"
    assert messages[0].payload["source_config_revision"] == "rev-2026-05-02-001-knx-main"


def test_config_delivery_records_are_derived_from_bundle(tmp_path: Path) -> None:
    settings = make_settings(tmp_path, config_delivery="kafka", publish_config=False)

    records = config_delivery_records(settings)

    assert [record.key for record in records] == [
        "tenant-001|demo-stand-01|manual-edge-demo|agent_runtime",
        "tenant-001|demo-stand-01|manual-edge-demo|source:knx_main",
    ]
    assert records[0].topic == "idp.edge.configs.v1"
    assert records[0].payload["message_type"] == (
        "idp.edge.config.delivery.v1"
    )
    assert records[0].payload["config_scope"] == "agent_runtime"
    assert records[0].payload["payload_message_type"] == "idp.edge.agent-runtime-config.v1"
    assert records[0].payload["target_mqtt_topic"] == (
        "idp/v1/agents/manual-edge-demo/config/agent-runtime"
    )
    assert records[1].payload["config_scope"] == "source:knx_main"
    assert records[1].payload["source_config_revision"] == (
        "rev-2026-05-02-001-knx-main"
    )
    assert records[1].payload["payload"]["message_type"] == (
        "idp.edge.source-config.v1"
    )


def test_settings_from_args_rejects_username_without_password(tmp_path: Path) -> None:
    class Args:
        bundle_config = _write_bundle(tmp_path)
        broker = "mqtt://localhost:1883"
        kafka_bootstrap_servers = "localhost:19092"
        kafka_client_id = "demo-kafka-client"
        config_registry_url = "http://localhost:8000"
        config_delivery = "mqtt"
        config_projection_timeout_seconds = 15.0
        username = "demo-user"
        password = None
        topic_root = "idp/v1"
        source_id = None
        client_id = "demo-client"
        interval_seconds = 2.0
        count = 0
        temperature_base = 23.0
        temperature_amplitude = 1.8
        temperature_period = 8.0
        no_config = False
        no_status = False
        retained_refresh_seconds = 30.0

    with pytest.raises(ValueError, match="--password is required"):
        settings_from_args(Args())
