from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Protocol


def now_utc_iso() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class RuntimePort(Protocol):
    def now_utc_iso(self) -> str: ...

    def monotonic(self) -> float: ...

    def sleep(self, seconds: float) -> None: ...


class SystemRuntime:
    def now_utc_iso(self) -> str:
        return now_utc_iso()

    def monotonic(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)
