from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TelegramEvent:
    rendered: str
    source_address: str | None
    destination_address: str | None
    payload: str | None


@dataclass(frozen=True)
class SignalUpdate:
    address: str
    value: object | None
    telegram: str
    source_address: str | None


@dataclass(frozen=True)
class ReadResult:
    address: str
    telegram: str
    update: SignalUpdate | None


@dataclass
class WatchState:
    address: str
    value: object | None = None
    update_count: int = 0
    last_telegram: str | None = None

    def register(self, update: SignalUpdate) -> None:
        self.value = update.value
        self.update_count += 1
        self.last_telegram = update.telegram

    def summary(self) -> str:
        return (
            f"address={self.address} "
            f"value={self.value!r} "
            f"updates={self.update_count} "
            f"last_telegram={self.last_telegram}"
        )


@dataclass(frozen=True)
class FeedbackSnapshot:
    is_on: bool | None
    last_telegram: str | None
