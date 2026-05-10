from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable

from knx_demo.application.ports import BlinkGateway, EventLogger
from knx_demo.domain.blink import build_steps, calculate_total_duration
from knx_demo.domain.profiles import EndpointProfile


@dataclass(frozen=True)
class BlinkMelodyCommand:
    profile: EndpointProfile
    switch_address: str
    feedback_address: str
    rhythm: str
    repeats: int
    unit: float
    prepare_off_seconds: float
    finish_off_seconds: float
    max_seconds: float


AsyncSleep = Callable[[float], Awaitable[None]]


async def run_blink_melody(
    command: BlinkMelodyCommand,
    gateway: BlinkGateway,
    logger: EventLogger,
    sleep: AsyncSleep = asyncio.sleep,
) -> None:
    steps = build_steps(
        rhythm=command.rhythm,
        unit=command.unit,
        repeats=command.repeats,
        finish_off_seconds=command.finish_off_seconds,
    )
    total_duration = calculate_total_duration(command.prepare_off_seconds, steps)
    if total_duration > command.max_seconds:
        raise ValueError(
            "Refusing to run demo: calculated duration %.2fs exceeds limit %.2fs"
            % (total_duration, command.max_seconds)
        )

    feedback_updates = 0

    def on_connection_state(state: str) -> None:
        logger.log(f"CONNECTION_STATE {state}")

    def on_telegram(event: object) -> None:
        nonlocal feedback_updates
        rendered = getattr(event, "rendered", str(event))
        logger.log(f"TELEGRAM {rendered}")
        if getattr(event, "destination_address", None) == command.feedback_address:
            feedback_updates += 1

    def on_feedback(snapshot: object) -> None:
        logger.log(
            "FEEDBACK_UPDATE is_on=%s last_telegram=%s"
            % (
                getattr(snapshot, "is_on", None),
                getattr(snapshot, "last_telegram", None),
            )
        )

    gateway.set_connection_state_handler(on_connection_state)
    gateway.set_telegram_handler(on_telegram)
    gateway.set_feedback_handler(on_feedback)

    try:
        await gateway.start()
        logger.log(
            "CONNECTED gateway=%s:%s route_back=%s assigned_address=%s rhythm=%s repeats=%s total=%.2fs"
            % (
                command.profile.gateway_ip,
                command.profile.gateway_port,
                command.profile.route_back,
                gateway.current_address,
                command.rhythm,
                command.repeats,
                total_duration,
            )
        )

        await gateway.set_off()
        logger.log("PREPARE force_off")
        await sleep(command.prepare_off_seconds)

        for index, step in enumerate(steps, start=1):
            if step.state:
                await gateway.set_on()
                logger.log(
                    "STEP %02d/%02d ON duration=%.2fs label=%s"
                    % (index, len(steps), step.duration, step.label)
                )
            else:
                await gateway.set_off()
                logger.log(
                    "STEP %02d/%02d OFF duration=%.2fs label=%s"
                    % (index, len(steps), step.duration, step.label)
                )
            await sleep(step.duration)

        await gateway.set_off()
        logger.log("DONE final_force_off")
        await sleep(0.5)
        snapshot = gateway.feedback_snapshot()
        logger.log(
            "SUMMARY feedback_updates=%s feedback_is_on=%s feedback_last_telegram=%s"
            % (
                feedback_updates,
                snapshot.is_on,
                snapshot.last_telegram,
            )
        )
    finally:
        await gateway.stop()
