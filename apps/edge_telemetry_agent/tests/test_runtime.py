from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from edge_telemetry_agent.application.configuration import build_agent_runtime_config
from edge_telemetry_agent.application.runtime import EdgeRuntime
from edge_telemetry_agent.domain.events import Observation
from edge_telemetry_agent.infrastructure.synthetic_knx import (
    SyntheticKnxObservationClient,
)


class FakeObservationStream:
    def __init__(self, observations: list[Observation]) -> None:
        self._observations = observations

    async def observations(self) -> AsyncIterator[Observation]:
        for observation in self._observations:
            yield observation


class FakeOutbox:
    def __init__(self) -> None:
        self.events: list[object] = []

    def append(self, event, *, available_at=None) -> int:
        self.events.append(event)
        return len(self.events)


class FakeDeliveryWorker:
    def __init__(self) -> None:
        self.calls = 0

    def deliver_once(self, *, limit: int = 100, lease_seconds: int = 60):
        self.calls += 1
        return type(
            "DeliveryResult",
            (),
            {
                "reserved_count": 1,
                "published_count": 1,
                "retry_count": 0,
                "dead_letter_count": 0,
            },
        )()


class BrokenObservationStream:
    async def observations(self) -> AsyncIterator[Observation]:
        raise RuntimeError("southbound source failed")
        yield  # pragma: no cover


def test_runtime_processes_southbound_observations_through_outbox_delivery(
    tmp_path,
) -> None:
    asyncio.run(_assert_runtime_processes_southbound_observations(tmp_path))


async def _assert_runtime_processes_southbound_observations(tmp_path) -> None:
    runtime_config = _runtime_config(tmp_path)
    outbox = FakeOutbox()
    delivery = FakeDeliveryWorker()
    source = FakeObservationStream(
        [
            Observation(
                source_id="knx_synthetic",
                point_ref="1/0/1",
                observation_mode="listen",
                value=22.5,
                value_raw="22.5",
            ),
            Observation(
                source_id="knx_synthetic",
                point_ref="1/0/4",
                observation_mode="listen",
                value=True,
                value_raw="true",
            ),
        ]
    )

    stats = await EdgeRuntime(
        runtime_config,
        observation_streams=[source],
        outbox=outbox,
        delivery_worker=delivery,
    ).run_until_streams_complete()

    assert stats.observations == 2
    assert stats.events_enqueued == 1
    assert stats.suppressed == {"command_point": 1}
    assert stats.delivery_published == 1
    assert len(outbox.events) == 1
    assert outbox.events[0].source_id == "knx_synthetic"
    assert outbox.events[0].point_ref == "1/0/1"
    assert delivery.calls == 1


def test_runtime_propagates_southbound_stream_errors(tmp_path) -> None:
    asyncio.run(_assert_runtime_propagates_southbound_stream_errors(tmp_path))


async def _assert_runtime_propagates_southbound_stream_errors(tmp_path) -> None:
    edge_runtime = EdgeRuntime(
        _runtime_config(tmp_path),
        observation_streams=[BrokenObservationStream()],
        outbox=FakeOutbox(),
        delivery_worker=FakeDeliveryWorker(),
    )

    try:
        await edge_runtime.run_until_streams_complete()
    except RuntimeError as exc:
        assert str(exc) == "southbound source failed"
    else:  # pragma: no cover
        raise AssertionError("expected southbound source error")
    assert edge_runtime.stats().errors == 1


def test_synthetic_knx_client_parses_emulator_json_lines() -> None:
    asyncio.run(_assert_synthetic_knx_client_parses_emulator_json_lines())


async def _assert_synthetic_knx_client_parses_emulator_json_lines() -> None:
    async def handle_client(
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        del reader
        writer.write(
            json.dumps(
                {
                    "source_id": "knx_synthetic",
                    "point_ref": "1/0/1",
                    "observation_mode": "read_on_start",
                    "value": 21.75,
                    "value_raw": "21.75",
                    "quality": "good",
                    "ts": "2026-05-10T12:00:00Z",
                }
            ).encode()
            + b"\n"
        )
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(handle_client, "127.0.0.1", 0)
    port = int(server.sockets[0].getsockname()[1])
    client = SyntheticKnxObservationClient(
        source_id="knx_synthetic",
        host="127.0.0.1",
        port=port,
    )
    try:
        observations = [item async for item in client.observations()]
    finally:
        server.close()
        await server.wait_closed()

    assert len(observations) == 1
    assert observations[0].source_id == "knx_synthetic"
    assert observations[0].point_ref == "1/0/1"
    assert observations[0].observation_mode == "read_on_start"
    assert observations[0].value == 21.75
    assert observations[0].observed_at.isoformat() == "2026-05-10T12:00:00+00:00"


def _runtime_config(tmp_path):
    return build_agent_runtime_config(
        bootstrap_data={
            "agent_id": "edge-synthetic-01",
            "delivery": {
                "transport": "mqtt",
                "mqtt": {
                    "enabled": True,
                    "version": "5.0",
                    "broker": "mqtt://127.0.0.1:1883",
                    "topic_root": "idp/v1",
                    "client_id_prefix": "edge-telemetry-agent",
                    "username_env": None,
                    "password_env": None,
                    "qos": 1,
                    "clean_start": True,
                    "session_expiry_seconds": 0,
                    "telemetry_message_expiry_seconds": 86400,
                    "connect_timeout_seconds": 5,
                    "retry_backoff_seconds": [1, 5],
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
        },
        agent_runtime_data={
            "message_type": "idp.edge.agent-runtime-config.v1",
            "tenant_id": "synthetic-tenant",
            "asset_id": "mall-synthetic-01",
            "agent_id": "edge-synthetic-01",
            "config_revision": "synthetic-test",
            "issued_at": "2026-05-10T12:00:00Z",
            "sources": [
                {
                    "source_id": "knx_synthetic",
                    "source_config_revision": "synthetic-test-knx_synthetic",
                    "enabled": True,
                }
            ],
        },
        source_documents=[
            {
                "message_type": "idp.edge.source-config.v1",
                "tenant_id": "synthetic-tenant",
                "asset_id": "mall-synthetic-01",
                "agent_id": "edge-synthetic-01",
                "config_revision": "synthetic-test",
                "source_id": "knx_synthetic",
                "source_config_revision": "synthetic-test-knx_synthetic",
                "source_type": "knx",
                "enabled": True,
                "connection": {
                    "mode": "synthetic",
                    "gateway_ip": "127.0.0.1",
                    "gateway_port": 3671,
                },
                "acquisition_defaults": {
                    "listen": True,
                    "read_on_start": False,
                    "periodic_interval_seconds": 60,
                },
                "publish_defaults": {
                    "enabled": True,
                    "change_threshold": None,
                },
                "points": [
                    {
                        "point_key": "1%2F0%2F1",
                        "point_ref": "1/0/1",
                        "name": "Температура воздуха",
                        "description": "Периодический опрос: 60 c",
                        "value_type": "number",
                        "value_model": "knx.dpt.9.001",
                        "signal_type": "sensor",
                        "unit": "C",
                        "acquisition": {
                            "listen": True,
                            "read_on_start": True,
                            "periodic_interval_seconds": 60,
                        },
                        "publish": {
                            "enabled": True,
                            "change_threshold": 0.5,
                        },
                        "tags": {"generated_by": "idp_synthetic_config"},
                    },
                    {
                        "point_key": "1%2F0%2F4",
                        "point_ref": "1/0/4",
                        "name": "Команда освещения",
                        "description": "Командная точка",
                        "value_type": "boolean",
                        "value_model": "knx.dpt.1.001",
                        "signal_type": "command",
                        "unit": None,
                        "acquisition": {
                            "listen": True,
                            "read_on_start": False,
                            "periodic_interval_seconds": 300,
                        },
                        "publish": {
                            "enabled": False,
                            "change_threshold": None,
                        },
                        "tags": {"generated_by": "idp_synthetic_config"},
                    },
                ],
            }
        ],
    )
