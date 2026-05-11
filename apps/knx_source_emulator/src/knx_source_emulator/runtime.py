from __future__ import annotations

import asyncio
import contextlib
import json
import math
import random
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TextIO

from idp_synthetic_config.models import (
    JsonObject,
    SyntheticModel,
    SyntheticPoint,
    SyntheticSource,
    ValueProfile,
)

ScalarValue = bool | int | float | str


@dataclass(frozen=True)
class EmulatorOptions:
    host: str = "127.0.0.1"
    port: int = 3671
    interval_seconds: float = 60.0
    time_scale: float = 60.0
    log_every_seconds: float = 10.0
    seed: int | None = None


@dataclass(frozen=True)
class EmulatorPoint:
    source_id: str
    point_id: str
    point_key: str
    point_ref: str
    name: str
    description: str | None
    value_type: str
    value_model: str
    signal_type: str
    unit: str | None
    periodic_interval_seconds: float
    read_on_start: bool
    publish_enabled: bool
    publish_change_threshold: float | None
    device_id: str | None
    value_profile: ValueProfile

    @property
    def emits_telemetry(self) -> bool:
        return self.signal_type != "command" and self.publish_enabled


@dataclass(frozen=True)
class EmulatorModel:
    source: SyntheticSource
    points: tuple[EmulatorPoint, ...]
    seed: int

    @property
    def telemetry_points(self) -> tuple[EmulatorPoint, ...]:
        return tuple(point for point in self.points if point.emits_telemetry)

    @property
    def read_on_start_points(self) -> tuple[EmulatorPoint, ...]:
        return tuple(point for point in self.telemetry_points if point.read_on_start)


@dataclass
class EmulatorStats:
    devices: int = 0
    points: int = 0
    knx_events: int = 0
    reads: int = 0
    writes: int = 0
    connected_agents: int = 0
    errors: int = 0

    def as_key_values(self) -> str:
        return " ".join(
            (
                f"devices={self.devices}",
                f"points={self.points}",
                f"knx_events={self.knx_events}",
                f"reads={self.reads}",
                f"writes={self.writes}",
                f"connected_agents={self.connected_agents}",
                f"errors={self.errors}",
            )
        )


def build_emulator_model(model: SyntheticModel) -> EmulatorModel:
    knx_sources = [source for source in model.sources if source.source_type == "knx"]
    if len(knx_sources) != 1:
        raise ValueError("synthetic model must contain exactly one KNX source")
    source = knx_sources[0]
    profiles = {profile.point_id: profile for profile in model.value_profiles}
    points = tuple(
        _emulator_point(source_id=source.source_id, point=point, profiles=profiles)
        for point in source.points
    )
    return EmulatorModel(source=source, points=points, seed=model.seed)


def plan_document(model: SyntheticModel, *, dry_run: bool) -> JsonObject:
    emulator_model = build_emulator_model(model)
    return {
        "dry_run": dry_run,
        "seed": model.seed,
        "tenant": model.tenant.to_dict(),
        "asset": model.asset.to_dict(),
        "agent": model.agent.to_dict(),
        "devices": [device.to_dict() for device in model.devices],
        "sources": [
            {
                "source_id": emulator_model.source.source_id,
                "source_type": emulator_model.source.source_type,
                "name": emulator_model.source.name,
                "description": emulator_model.source.description,
                "connection": dict(emulator_model.source.connection_json),
                "points": [
                    {
                        "point_id": point.point_id,
                        "point_key": point.point_key,
                        "point_ref": point.point_ref,
                        "name": point.name,
                        "description": point.description,
                        "periodic_interval_seconds": point.periodic_interval_seconds,
                        "change_threshold": point.publish_change_threshold,
                        "read_on_start": point.read_on_start,
                        "signal_type": point.signal_type,
                        "value_type": point.value_type,
                        "value_model": point.value_model,
                    }
                    for point in emulator_model.points
                ],
            }
        ],
        "value_profiles": [profile.to_dict() for profile in model.value_profiles],
    }


class ValueProfileEngine:
    def __init__(self, *, seed: int) -> None:
        self._random = random.Random(seed)
        self._steps: dict[str, int] = {}
        self._numeric_values: dict[str, float] = {}
        self._boolean_values: dict[str, bool] = {}

    def next_value(self, point: EmulatorPoint) -> ScalarValue:
        step = self._steps.get(point.point_id, 0)
        self._steps[point.point_id] = step + 1
        if point.value_type == "number":
            return self._next_number(point, step=step)
        if point.value_type == "boolean":
            return self._next_boolean(point, step=step)
        if point.value_type == "string":
            return self._next_string(point, step=step)
        raise ValueError(f"unsupported value_type {point.value_type!r}")

    def _next_number(self, point: EmulatorPoint, *, step: int) -> float:
        parameters = point.value_profile.parameters
        base = float(parameters.get("base", 0.0))
        amplitude = abs(float(parameters.get("amplitude", 1.0))) or 1.0
        threshold = point.publish_change_threshold
        previous = self._numeric_values.get(point.point_id, base)
        if threshold is None or threshold <= 0:
            period_seconds = max(float(parameters.get("period_seconds", 60.0)), 1.0)
            phase = (step % int(period_seconds)) / period_seconds
            value = base + math.sin(phase * math.tau) * amplitude
        else:
            small_delta = threshold / 2
            large_delta = threshold * 1.5
            direction = -1 if step % 4 == 3 else 1
            delta = small_delta if step % 3 == 1 else large_delta
            value = previous + direction * delta
            if abs(value - base) > amplitude:
                value = base - direction * small_delta
        value = round(value, 3)
        self._numeric_values[point.point_id] = value
        return value

    def _next_boolean(self, point: EmulatorPoint, *, step: int) -> bool:
        if point.point_id not in self._boolean_values:
            ratio = float(point.value_profile.parameters.get("true_ratio", 0.5))
            self._boolean_values[point.point_id] = self._random.random() < ratio
        if step > 0 and step % 3 == 0:
            self._boolean_values[point.point_id] = not self._boolean_values[point.point_id]
        return self._boolean_values[point.point_id]

    def _next_string(self, point: EmulatorPoint, *, step: int) -> str:
        values = point.value_profile.parameters.get("values")
        if not isinstance(values, list) or not values:
            return "норма"
        value = values[step % len(values)]
        return str(value)


class AsyncKnxEmulator:
    def __init__(
        self,
        model: EmulatorModel,
        options: EmulatorOptions | None = None,
        *,
        stdout: TextIO | None = None,
    ) -> None:
        self._model = model
        self._options = options or EmulatorOptions()
        self._stdout = stdout or sys.stdout
        self._server: asyncio.AbstractServer | None = None
        self._clients: set[asyncio.StreamWriter] = set()
        self._tasks: list[asyncio.Task[None]] = []
        self._engine = ValueProfileEngine(seed=self._options.seed or model.seed)
        self.stats = EmulatorStats(
            devices=len(
                {point.device_id for point in model.points if point.device_id is not None}
            ),
            points=len(model.points),
        )

    @property
    def bound_port(self) -> int | None:
        if self._server is None or not self._server.sockets:
            return None
        return int(self._server.sockets[0].getsockname()[1])

    async def __aenter__(self) -> AsyncKnxEmulator:
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        await self.stop()

    async def start(self) -> None:
        self._server = await asyncio.start_server(
            self._handle_client,
            self._options.host,
            self._options.port,
        )
        self._tasks = [
            asyncio.create_task(self._schedule_point(point), name=f"knx:{point.point_ref}")
            for point in self._model.telemetry_points
        ]
        self._tasks.append(
            asyncio.create_task(self._log_stats(), name="knx:stats"),
        )
        self._write_log(
            "event=emulator_started "
            f"host={self._options.host} port={self.bound_port} "
            f"{self.stats.as_key_values()}"
        )

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._tasks = []
        for writer in tuple(self._clients):
            await self._close_writer(writer)
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        self._write_log(f"event=emulator_stopped {self.stats.as_key_values()}")

    async def run_until_cancelled(self) -> None:
        if self._server is None:
            await self.start()
        await asyncio.Event().wait()

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        del reader
        self._clients.add(writer)
        self.stats.connected_agents = len(self._clients)
        try:
            for point in self._model.read_on_start_points:
                await self._write_event(writer, point, observation_mode="read_on_start")
            await writer.drain()
            await writer.wait_closed()
        except (ConnectionError, OSError):
            self.stats.errors += 1
        finally:
            self._clients.discard(writer)
            self.stats.connected_agents = len(self._clients)

    async def _schedule_point(self, point: EmulatorPoint) -> None:
        interval = point.periodic_interval_seconds or self._options.interval_seconds
        interval = interval if interval > 0 else self._options.interval_seconds
        wall_interval = max(0.01, interval / max(self._options.time_scale, 0.001))
        await asyncio.sleep(wall_interval)
        while True:
            await self._broadcast(point, observation_mode="periodic_read")
            await asyncio.sleep(wall_interval)

    async def _broadcast(self, point: EmulatorPoint, *, observation_mode: str) -> None:
        for writer in tuple(self._clients):
            try:
                await self._write_event(writer, point, observation_mode=observation_mode)
                await writer.drain()
            except (ConnectionError, OSError):
                self.stats.errors += 1
                self._clients.discard(writer)

    async def _write_event(
        self,
        writer: asyncio.StreamWriter,
        point: EmulatorPoint,
        *,
        observation_mode: str,
    ) -> None:
        value = self._engine.next_value(point)
        payload = _event_payload(
            point,
            value=value,
            observation_mode=observation_mode,
        )
        writer.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode())
        writer.write(b"\n")
        self.stats.knx_events += 1
        if observation_mode == "read_on_start":
            self.stats.reads += 1

    async def _close_writer(self, writer: asyncio.StreamWriter) -> None:
        with contextlib.suppress(Exception):
            writer.close()
            await writer.wait_closed()

    async def _log_stats(self) -> None:
        while True:
            await asyncio.sleep(self._options.log_every_seconds)
            self._write_log(f"event=emulator_stats {self.stats.as_key_values()}")

    def _write_log(self, line: str) -> None:
        print(line, file=self._stdout)


def _emulator_point(
    *,
    source_id: str,
    point: SyntheticPoint,
    profiles: dict[str, ValueProfile],
) -> EmulatorPoint:
    profile = profiles.get(point.point_id)
    if profile is None:
        raise ValueError(f"value profile is missing for point_id={point.point_id}")
    if profile.value_type != point.value_type:
        raise ValueError(f"value profile value_type mismatch for point_id={point.point_id}")
    interval = point.acquisition.get("periodic_interval_seconds")
    if isinstance(interval, bool) or not isinstance(interval, int | float) or interval <= 0:
        raise ValueError(
            "generated point acquisition.periodic_interval_seconds must be positive: "
            f"point_id={point.point_id}"
        )
    change_threshold = point.publish.get("change_threshold")
    if change_threshold is not None:
        if isinstance(change_threshold, bool) or not isinstance(change_threshold, int | float):
            raise ValueError(f"change_threshold must be numeric: point_id={point.point_id}")
        change_threshold = float(change_threshold)
    return EmulatorPoint(
        source_id=source_id,
        point_id=point.point_id,
        point_key=point.point_key,
        point_ref=point.point_ref,
        name=point.name,
        description=point.description,
        value_type=point.value_type,
        value_model=point.value_model,
        signal_type=point.signal_type,
        unit=point.unit,
        periodic_interval_seconds=float(interval),
        read_on_start=bool(point.acquisition.get("read_on_start")),
        publish_enabled=bool(point.publish.get("enabled")),
        publish_change_threshold=change_threshold,
        device_id=point.tags.get("device_id"),
        value_profile=profile,
    )


def _event_payload(
    point: EmulatorPoint,
    *,
    value: ScalarValue,
    observation_mode: str,
) -> JsonObject:
    return {
        "source_id": point.source_id,
        "point_ref": point.point_ref,
        "point_key": point.point_key,
        "observation_mode": observation_mode,
        "value": value,
        "value_raw": _raw_value(value),
        "quality": "good",
        "ts": datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "name": point.name,
        "description": point.description,
        "signal_type": point.signal_type,
        "value_model": point.value_model,
    }


def _raw_value(value: ScalarValue) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


async def run_emulator(
    model: EmulatorModel,
    options: EmulatorOptions,
    *,
    duration_seconds: float | None = None,
    stdout: TextIO | None = None,
) -> EmulatorStats:
    emulator = AsyncKnxEmulator(model, options, stdout=stdout)
    async with emulator:
        if duration_seconds is None:
            await emulator.run_until_cancelled()
        else:
            await asyncio.sleep(max(duration_seconds, 0.0))
    return emulator.stats


def point_refs(points: Iterable[EmulatorPoint]) -> tuple[str, ...]:
    return tuple(point.point_ref for point in points)
