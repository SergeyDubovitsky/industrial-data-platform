from __future__ import annotations

import asyncio
import json
import threading

from idp_synthetic_config.generator import GeneratorOptions, generate_synthetic_config
from knx_source_emulator.runtime import (
    AsyncKnxEmulator,
    EmulatorOptions,
    ValueProfileEngine,
    build_emulator_model,
)


def test_emulator_model_consumes_generated_knx_config_and_profiles() -> None:
    generated = generate_synthetic_config(
        GeneratorOptions(seed=7, devices=2, tags_per_device=10)
    )

    model = build_emulator_model(generated)

    assert model.source.source_id == "knx_synthetic"
    assert len(model.points) == 20
    assert {point.signal_type for point in model.points} == {
        "command",
        "feedback",
        "sensor",
        "status",
    }
    assert all(point.point_ref.count("/") == 2 for point in model.points)
    assert all(point.value_profile.point_id == point.point_id for point in model.points)
    assert not any(point.signal_type == "command" for point in model.telemetry_points)
    assert model.telemetry_points[0].periodic_interval_seconds == (
        generated.sources[0].points[0].acquisition["periodic_interval_seconds"]
    )


def test_numeric_value_profile_crosses_and_stays_below_generated_threshold() -> None:
    generated = generate_synthetic_config(
        GeneratorOptions(seed=13, devices=1, tags_per_device=1)
    )
    model = build_emulator_model(generated)
    point = model.telemetry_points[0]
    assert point.publish_change_threshold is not None
    engine = ValueProfileEngine(seed=generated.seed)

    values = [engine.next_value(point) for _ in range(4)]
    deltas = [
        abs(float(current) - float(previous))
        for previous, current in zip(values, values[1:], strict=False)
    ]

    assert any(delta < point.publish_change_threshold for delta in deltas)
    assert any(delta >= point.publish_change_threshold for delta in deltas)


def test_async_emulator_streams_read_on_start_and_periodic_events() -> None:
    asyncio.run(_assert_async_emulator_streams_read_on_start_and_periodic_events())


async def _assert_async_emulator_streams_read_on_start_and_periodic_events() -> None:
    generated = generate_synthetic_config(
        GeneratorOptions(seed=23, devices=1, tags_per_device=2)
    )
    model = build_emulator_model(generated)
    emulator = AsyncKnxEmulator(
        model,
        EmulatorOptions(
            host="127.0.0.1",
            port=0,
            interval_seconds=0.05,
            time_scale=10_000.0,
            log_every_seconds=3600.0,
        ),
    )

    before_threads = threading.active_count()
    async with emulator:
        assert emulator.bound_port is not None
        reader, writer = await asyncio.open_connection("127.0.0.1", emulator.bound_port)
        try:
            first_line = await asyncio.wait_for(reader.readline(), timeout=2)
            second_line = await asyncio.wait_for(reader.readline(), timeout=2)
        finally:
            writer.close()
            await writer.wait_closed()

    first_payload = json.loads(first_line.decode())
    second_payload = json.loads(second_line.decode())
    assert first_payload["observation_mode"] == "read_on_start"
    assert first_payload["source_id"] == "knx_synthetic"
    assert first_payload["point_ref"]
    assert second_payload["observation_mode"] in {"periodic_read", "read_on_start"}
    assert threading.active_count() <= before_threads + 1
