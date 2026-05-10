from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable

from knx_demo.application.ports import EventLogger, SignalReaderGateway
from knx_demo.domain.profiles import EndpointProfile
from knx_demo.domain.telemetry import WatchState


@dataclass(frozen=True)
class ReadSignalsCommand:
    profile: EndpointProfile
    addresses: tuple[str, ...]
    payload_length: int
    read_timeout: float
    monitor_seconds: float


AsyncSleep = Callable[[float], Awaitable[None]]


async def run_read_signals(
    command: ReadSignalsCommand,
    gateway: SignalReaderGateway,
    logger: EventLogger,
    sleep: AsyncSleep = asyncio.sleep,
) -> None:
    watches = {address: WatchState(address=address) for address in command.addresses}

    def log_telegram(rendered: str) -> None:
        logger.log(f"TELEGRAM {rendered}")

    def on_connection_state(state: str) -> None:
        logger.log(f"CONNECTION_STATE {state}")

    def on_telegram(event: object) -> None:
        rendered = getattr(event, "rendered", str(event))
        log_telegram(rendered)

    def on_update(update: object) -> None:
        address = getattr(update, "address", None)
        watch = watches.get(address)
        if watch is None:
            return
        watch.register(update)
        logger.log(f"STATE_UPDATE {watch.summary()}")

    gateway.set_connection_state_handler(on_connection_state)
    gateway.set_telegram_handler(on_telegram)
    gateway.set_update_handler(on_update)

    try:
        await gateway.start()
        logger.log(
            "CONNECTED gateway=%s:%s route_back=%s assigned_address=%s"
            % (
                command.profile.gateway_ip,
                command.profile.gateway_port,
                command.profile.route_back,
                gateway.current_address,
            )
        )

        for watch in watches.values():
            logger.log(f"READ_REQUEST address={watch.address}")
            result = await gateway.read(watch.address, command.read_timeout)
            if result is None:
                logger.log(f"READ_TIMEOUT address={watch.address}")
                continue
            if result.update is not None:
                watch.register(result.update)
                logger.log(f"READ_RESPONSE {watch.summary()}")
            else:
                logger.log(
                    "READ_RESPONSE address=%s telegram=%s"
                    % (watch.address, result.telegram)
                )

        if command.monitor_seconds > 0:
            logger.log(f"MONITOR start seconds={command.monitor_seconds}")
            await sleep(command.monitor_seconds)
            logger.log("MONITOR done")
    finally:
        await gateway.stop()
        for watch in watches.values():
            logger.log(f"SUMMARY {watch.summary()}")
