from __future__ import annotations

import asyncio
from dataclasses import dataclass

from knx_demo.application.read_signals import ReadSignalsCommand, run_read_signals
from knx_demo.domain.profiles import EndpointProfile
from knx_demo.domain.telemetry import ReadResult, SignalUpdate, TelegramEvent


class FakeLogger:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def log(self, message: str) -> None:
        self.messages.append(message)


@dataclass
class FakeSignalReaderGateway:
    current_address: str | None = "1.1.250"
    read_results: dict[str, ReadResult | None] | None = None

    def __post_init__(self) -> None:
        self.connection_state_handler = lambda state: None
        self.telegram_handler = lambda event: None
        self.update_handler = lambda update: None
        self.started = False
        self.stopped = False

    def set_connection_state_handler(self, handler):
        self.connection_state_handler = handler

    def set_telegram_handler(self, handler):
        self.telegram_handler = handler

    def set_update_handler(self, handler):
        self.update_handler = handler

    async def start(self) -> None:
        self.started = True
        self.connection_state_handler("CONNECTING")
        self.connection_state_handler("CONNECTED")

    async def stop(self) -> None:
        self.stopped = True
        self.connection_state_handler("DISCONNECTED")

    async def read(self, address: str, timeout: float) -> ReadResult | None:
        del timeout
        assert self.read_results is not None
        return self.read_results[address]

    def emit_telegram(self, rendered: str, destination_address: str) -> None:
        self.telegram_handler(
            TelegramEvent(
                rendered=rendered,
                source_address="1.1.4",
                destination_address=destination_address,
                payload="payload",
            )
        )

    def emit_update(self, address: str, value: object, telegram: str) -> None:
        self.update_handler(
            SignalUpdate(
                address=address,
                value=value,
                telegram=telegram,
                source_address="1.1.4",
            )
        )


def _command(*addresses: str, monitor_seconds: float = 0.0) -> ReadSignalsCommand:
    return ReadSignalsCommand(
        profile=EndpointProfile("203.0.113.234", 7171, True),
        addresses=tuple(addresses),
        payload_length=0,
        read_timeout=2.0,
        monitor_seconds=monitor_seconds,
    )


def test_run_read_signals_logs_read_response_and_summary() -> None:
    gateway = FakeSignalReaderGateway(
        read_results={
            "0/0/7": ReadResult(
                address="0/0/7",
                telegram="<Telegram response>",
                update=SignalUpdate(
                    address="0/0/7",
                    value=True,
                    telegram="<Telegram response>",
                    source_address="1.1.2",
                ),
            )
        }
    )
    logger = FakeLogger()

    asyncio.run(run_read_signals(_command("0/0/7"), gateway, logger))

    assert gateway.started is True
    assert gateway.stopped is True
    assert "CONNECTED gateway=203.0.113.234:7171 route_back=True assigned_address=1.1.250" in logger.messages
    assert "READ_REQUEST address=0/0/7" in logger.messages
    assert "READ_RESPONSE address=0/0/7 value=True updates=1 last_telegram=<Telegram response>" in logger.messages
    assert logger.messages[-1] == "SUMMARY address=0/0/7 value=True updates=1 last_telegram=<Telegram response>"


def test_run_read_signals_logs_raw_response_when_update_is_missing() -> None:
    gateway = FakeSignalReaderGateway(
        read_results={
            "0/0/1": ReadResult(
                address="0/0/1",
                telegram="<Telegram raw>",
                update=None,
            )
        }
    )
    logger = FakeLogger()

    asyncio.run(run_read_signals(_command("0/0/1"), gateway, logger))

    assert "READ_RESPONSE address=0/0/1 telegram=<Telegram raw>" in logger.messages


def test_run_read_signals_processes_passive_updates_during_monitor() -> None:
    gateway = FakeSignalReaderGateway(read_results={"2/0/0": None})
    logger = FakeLogger()

    async def fake_sleep(seconds: float) -> None:
        assert seconds == 1.5
        gateway.emit_telegram("<Telegram passive>", "2/0/0")
        gateway.emit_update("2/0/0", 3287, "<Telegram passive>")

    asyncio.run(
        run_read_signals(
            _command("2/0/0", monitor_seconds=1.5),
            gateway,
            logger,
            sleep=fake_sleep,
        )
    )

    assert "READ_TIMEOUT address=2/0/0" in logger.messages
    assert "TELEGRAM <Telegram passive>" in logger.messages
    assert "STATE_UPDATE address=2/0/0 value=3287 updates=1 last_telegram=<Telegram passive>" in logger.messages
    assert logger.messages[-1] == "SUMMARY address=2/0/0 value=3287 updates=1 last_telegram=<Telegram passive>"
