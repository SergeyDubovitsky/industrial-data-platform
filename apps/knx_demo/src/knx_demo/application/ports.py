from __future__ import annotations

from typing import Callable, Protocol

from knx_demo.domain.telemetry import (
    FeedbackSnapshot,
    ReadResult,
    SignalUpdate,
    TelegramEvent,
)


class EventLogger(Protocol):
    def log(self, message: str) -> None: ...


class SignalReaderGateway(Protocol):
    current_address: str | None

    def set_connection_state_handler(self, handler: Callable[[str], None]) -> None: ...

    def set_telegram_handler(self, handler: Callable[[TelegramEvent], None]) -> None: ...

    def set_update_handler(self, handler: Callable[[SignalUpdate], None]) -> None: ...

    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    async def read(self, address: str, timeout: float) -> ReadResult | None: ...


class BlinkGateway(Protocol):
    current_address: str | None

    def set_connection_state_handler(self, handler: Callable[[str], None]) -> None: ...

    def set_telegram_handler(self, handler: Callable[[TelegramEvent], None]) -> None: ...

    def set_feedback_handler(self, handler: Callable[[FeedbackSnapshot], None]) -> None: ...

    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    async def set_on(self) -> None: ...

    async def set_off(self) -> None: ...

    def feedback_snapshot(self) -> FeedbackSnapshot: ...
