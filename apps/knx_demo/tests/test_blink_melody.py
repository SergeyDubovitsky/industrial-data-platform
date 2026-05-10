from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import pytest

from knx_demo.application.blink_melody import BlinkMelodyCommand, run_blink_melody
from knx_demo.domain.blink import build_sos_steps
from knx_demo.domain.profiles import EndpointProfile
from knx_demo.domain.telemetry import FeedbackSnapshot, TelegramEvent


class FakeLogger:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def log(self, message: str) -> None:
        self.messages.append(message)


@dataclass
class FakeBlinkGateway:
    current_address: str | None = "1.1.251"
    actions: list[str] = field(default_factory=list)
    snapshot: FeedbackSnapshot = field(
        default_factory=lambda: FeedbackSnapshot(is_on=False, last_telegram=None)
    )

    def __post_init__(self) -> None:
        self.connection_state_handler = lambda state: None
        self.telegram_handler = lambda event: None
        self.feedback_handler = lambda snapshot: None
        self.started = False
        self.stopped = False

    def set_connection_state_handler(self, handler):
        self.connection_state_handler = handler

    def set_telegram_handler(self, handler):
        self.telegram_handler = handler

    def set_feedback_handler(self, handler):
        self.feedback_handler = handler

    async def start(self) -> None:
        self.started = True
        self.connection_state_handler("CONNECTING")
        self.connection_state_handler("CONNECTED")

    async def stop(self) -> None:
        self.stopped = True
        self.connection_state_handler("DISCONNECTED")

    async def set_on(self) -> None:
        self.actions.append("on")

    async def set_off(self) -> None:
        self.actions.append("off")

    def feedback_snapshot(self) -> FeedbackSnapshot:
        return self.snapshot

    def emit_feedback_telegram(self, value: str = "<Telegram feedback>") -> None:
        event = TelegramEvent(
            rendered=value,
            source_address="1.1.2",
            destination_address="0/0/7",
            payload="payload",
        )
        self.telegram_handler(event)

    def emit_feedback_snapshot(self, is_on: bool, telegram: str) -> None:
        self.snapshot = FeedbackSnapshot(is_on=is_on, last_telegram=telegram)
        self.feedback_handler(self.snapshot)


def _command(
    *,
    repeats: int = 1,
    unit: float = 0.1,
    max_seconds: float = 30.0,
) -> BlinkMelodyCommand:
    return BlinkMelodyCommand(
        profile=EndpointProfile("203.0.113.234", 7171, True),
        switch_address="0/0/1",
        feedback_address="0/0/7",
        rhythm="sos",
        repeats=repeats,
        unit=unit,
        prepare_off_seconds=0.2,
        finish_off_seconds=0.3,
        max_seconds=max_seconds,
    )


def test_build_sos_steps_produces_expected_shape() -> None:
    steps = build_sos_steps(unit=0.1, repeats=1, finish_off_seconds=0.3)

    assert len(steps) == 18
    assert steps[0].label == "S1"
    assert steps[-1].label == "finish_off"
    assert steps[-1].state is False


def test_run_blink_melody_executes_sequence_and_logs_summary() -> None:
    gateway = FakeBlinkGateway()
    logger = FakeLogger()

    async def fake_sleep(seconds: float) -> None:
        del seconds
        gateway.emit_feedback_telegram()
        gateway.emit_feedback_snapshot(is_on=False, telegram="<Feedback telegram>")

    asyncio.run(
        run_blink_melody(
            _command(),
            gateway=gateway,
            logger=logger,
            sleep=fake_sleep,
        )
    )

    assert gateway.started is True
    assert gateway.stopped is True
    assert gateway.actions[0] == "off"
    assert gateway.actions[-1] == "off"
    assert len(gateway.actions) == 20
    assert any(message.startswith("CONNECTED gateway=203.0.113.234:7171") for message in logger.messages)
    assert any(message.startswith("STEP 01/18 ON") for message in logger.messages)
    assert any(message == "DONE final_force_off" for message in logger.messages)
    assert any(
        message == "SUMMARY feedback_updates=20 feedback_is_on=False feedback_last_telegram=<Feedback telegram>"
        for message in logger.messages
    )


def test_run_blink_melody_rejects_overlong_sequences() -> None:
    gateway = FakeBlinkGateway()
    logger = FakeLogger()

    with pytest.raises(ValueError, match="Refusing to run demo"):
        asyncio.run(run_blink_melody(_command(repeats=10, unit=1.0, max_seconds=1.0), gateway, logger))

    assert gateway.started is False
