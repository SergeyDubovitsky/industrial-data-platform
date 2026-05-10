from __future__ import annotations

from datetime import datetime


def timestamp() -> str:
    return datetime.now().isoformat(timespec="seconds")


class ConsoleLogger:
    def log(self, message: str) -> None:
        print(f"{timestamp()} {message}", flush=True)
