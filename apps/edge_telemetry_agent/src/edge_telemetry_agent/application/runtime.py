from __future__ import annotations

import asyncio
from collections import Counter
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from typing import Protocol

from edge_telemetry_agent.application.delivery import DeliveryRunResult
from edge_telemetry_agent.application.processing import (
    ObservationProcessor,
    PointStateStore,
)
from edge_telemetry_agent.domain.config import AgentRuntimeConfig
from edge_telemetry_agent.domain.events import Observation, TelemetryEvent


class ObservationStream(Protocol):
    def observations(self) -> AsyncIterator[Observation]:
        ...


class RuntimeOutbox(Protocol):
    def append(self, event: TelemetryEvent, *, available_at=None) -> int:
        ...


class RuntimeDeliveryWorker(Protocol):
    def deliver_once(
        self,
        *,
        limit: int = 100,
        lease_seconds: int = 60,
    ) -> DeliveryRunResult:
        ...


@dataclass(frozen=True)
class EdgeRuntimeStats:
    observations: int = 0
    events_enqueued: int = 0
    delivery_reserved: int = 0
    delivery_published: int = 0
    delivery_retry: int = 0
    delivery_dead_letter: int = 0
    suppressed: dict[str, int] = field(default_factory=dict)
    errors: int = 0


class EdgeRuntime:
    def __init__(
        self,
        runtime_config: AgentRuntimeConfig,
        *,
        observation_streams: Sequence[ObservationStream],
        outbox: RuntimeOutbox,
        delivery_worker: RuntimeDeliveryWorker,
        state_store: PointStateStore | None = None,
        delivery_limit: int = 100,
        lease_seconds: int = 60,
    ) -> None:
        self._runtime_config = runtime_config
        self._observation_streams = tuple(observation_streams)
        self._outbox = outbox
        self._delivery_worker = delivery_worker
        self._delivery_limit = delivery_limit
        self._lease_seconds = lease_seconds
        self._processor = ObservationProcessor(
            runtime_config,
            agent_id=runtime_config.agent_id,
            state_store=state_store,
        )
        self._suppressed: Counter[str] = Counter()
        self._observations = 0
        self._events_enqueued = 0
        self._delivery_reserved = 0
        self._delivery_published = 0
        self._delivery_retry = 0
        self._delivery_dead_letter = 0
        self._errors = 0

    async def run_until_streams_complete(self) -> EdgeRuntimeStats:
        tasks = [
            asyncio.create_task(self._consume(stream), name=f"edge-stream-{index}")
            for index, stream in enumerate(self._observation_streams)
        ]
        if not tasks:
            return self._stats()
        try:
            await asyncio.gather(*tasks)
        except Exception:
            self._errors += 1
            for task in tasks:
                task.cancel()
            raise
        return self._stats()

    def stats(self) -> EdgeRuntimeStats:
        return self._stats()

    async def _consume(self, stream: ObservationStream) -> None:
        async for observation in stream.observations():
            self._observations += 1
            result = self._processor.process(observation)
            if result.event is None:
                reason = result.suppressed_reason or "unknown"
                self._suppressed[reason] += 1
                continue
            self._outbox.append(result.event, available_at=result.event.ts)
            self._events_enqueued += 1
            delivery_result = self._delivery_worker.deliver_once(
                limit=self._delivery_limit,
                lease_seconds=self._lease_seconds,
            )
            self._delivery_reserved += delivery_result.reserved_count
            self._delivery_published += delivery_result.published_count
            self._delivery_retry += delivery_result.retry_count
            self._delivery_dead_letter += delivery_result.dead_letter_count

    def _stats(self) -> EdgeRuntimeStats:
        return EdgeRuntimeStats(
            observations=self._observations,
            events_enqueued=self._events_enqueued,
            delivery_reserved=self._delivery_reserved,
            delivery_published=self._delivery_published,
            delivery_retry=self._delivery_retry,
            delivery_dead_letter=self._delivery_dead_letter,
            suppressed=dict(self._suppressed),
            errors=self._errors,
        )
