from __future__ import annotations

import argparse
import json
import os
import string
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Sequence

DEFAULT_CONFIG = Path(__file__).with_name("clickhouse-sink.telemetry-store-v1.json")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply local Kafka Connect connector config.")
    parser.add_argument("--connect-url", default=os.getenv("KAFKA_CONNECT_URL", "http://localhost:8083"))
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    args = parser.parse_args(argv)

    payload = _render_config(args.config)
    name = str(payload["name"])
    connect_url = str(args.connect_url).rstrip("/")

    _wait_for_connect(connect_url, timeout=args.timeout_seconds)
    _put_json(f"{connect_url}/connectors/{name}/config", payload["config"])
    print(f"Applied Kafka Connect connector config: {name}")
    return 0


def _render_config(path: Path) -> dict[str, Any]:
    defaults = {
        "KAFKA_CONNECTOR_NAME": os.getenv(
            "KAFKA_CONNECTOR_NAME",
            "idp-telemetry-store-telemetry-store-v1",
        ),
        "CLICKHOUSE_CONNECT_HOST": os.getenv("CLICKHOUSE_CONNECT_HOST", "clickhouse"),
        "CLICKHOUSE_CONNECT_PORT": os.getenv("CLICKHOUSE_CONNECT_PORT", "8123"),
        "CLICKHOUSE_CONNECT_SSL": os.getenv("CLICKHOUSE_CONNECT_SSL", "false"),
        "CLICKHOUSE_DATABASE": os.getenv("CLICKHOUSE_DATABASE", "idp"),
        "CLICKHOUSE_USER": os.getenv("CLICKHOUSE_USER", "idp"),
        "CLICKHOUSE_PASSWORD": os.getenv(
            "CLICKHOUSE_PASSWORD",
            "change-me-local-clickhouse",
        ),
    }
    rendered = string.Template(path.read_text(encoding="utf-8")).safe_substitute(
        {**defaults, **os.environ}
    )
    return json.loads(rendered)


def _wait_for_connect(connect_url: str, *, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    last_error = "Kafka Connect is not reachable yet."

    while time.monotonic() < deadline:
        try:
            _request("GET", f"{connect_url}/connectors")
            return
        except (OSError, urllib.error.URLError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        time.sleep(1)

    raise RuntimeError(
        f"Kafka Connect did not become ready within {timeout:.0f}s. "
        f"Last error: {last_error}"
    )


def _put_json(url: str, payload: dict[str, Any]) -> None:
    _request("PUT", url, payload)


def _request(method: str, url: str, payload: dict[str, Any] | None = None) -> str:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload, sort_keys=True).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} failed with HTTP {exc.code}: {body}") from exc


if __name__ == "__main__":
    raise SystemExit(main())
