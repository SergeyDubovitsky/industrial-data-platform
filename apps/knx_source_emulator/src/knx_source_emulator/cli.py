from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import os
import re
import signal
import sys
from datetime import datetime
from typing import Any, TextIO

from idp_synthetic_config.config_registry_seeder import (
    ConfigRegistryError,
    ConfigRegistryHttpClient,
    ConfigRegistrySeeder,
)
from idp_synthetic_config.generator import GeneratorOptions, generate_synthetic_config
from idp_synthetic_config.reset import DestructiveResetRefused, ResetPolicy
from knx_source_emulator.runtime import (
    EmulatorOptions,
    build_emulator_model,
    plan_document,
    run_emulator,
)


def main(
    argv: list[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    out = stdout or sys.stdout
    err = stderr or sys.stderr
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        return _dispatch(args, stdout=out, stderr=err)
    except (ConfigRegistryError, DestructiveResetRefused, ValueError, OSError) as exc:
        print(str(exc), file=err)
        return 2


def _dispatch(
    args: argparse.Namespace,
    *,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    if args.command == "plan":
        model = generate_synthetic_config(_generator_options(args))
        _write_document(plan_document(model, dry_run=args.dry_run), args.format, stdout)
        return 0
    if args.command == "seed-config":
        model = generate_synthetic_config(_generator_options(args))
        summary = _seed_config(model, args)
        _write_document(summary.to_dict(), args.format, stdout)
        return 0 if summary.ok else 1
    if args.command == "run":
        model = generate_synthetic_config(_generator_options(args))
        return _run_model(model, args, stdout=stdout, stderr=stderr)
    if args.command == "start":
        model = generate_synthetic_config(_generator_options(args))
        summary = _seed_config(model, args)
        _write_document(summary.to_dict(), args.format, stdout)
        if not summary.ok:
            return 1
        if args.retained_wait_seconds > 0:
            print(
                "event=waiting_for_retained_projection "
                f"seconds={args.retained_wait_seconds}",
                file=stdout,
            )
            asyncio.run(asyncio.sleep(args.retained_wait_seconds))
        return _run_model(model, args, stdout=stdout, stderr=stderr)
    raise ValueError(f"unknown command {args.command!r}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="knx-source-emulator",
        description="Local KNX-like source emulator for synthetic edge scenarios",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan = subparsers.add_parser("plan", help="Print emulator plan without side effects")
    _add_generator_args(plan)
    _add_format_arg(plan)
    plan.add_argument("--dry-run", action="store_true")

    seed_config = subparsers.add_parser(
        "seed-config",
        help="Generate and seed KNX config through idp-synthetic-config",
    )
    _add_generator_args(seed_config)
    _add_format_arg(seed_config)
    _add_seed_args(seed_config)

    run = subparsers.add_parser("run", help="Run local KNX-like event source")
    _add_generator_args(run)
    _add_runtime_args(run)

    start = subparsers.add_parser(
        "start",
        help="Seed config, wait for retained projection, then run emulator",
    )
    _add_generator_args(start)
    _add_format_arg(start)
    _add_seed_args(start)
    _add_runtime_args(start)
    start.add_argument(
        "--retained-wait-seconds",
        type=float,
        default=5.0,
        help="Local wait after render-config before KNX runtime starts.",
    )
    return parser


def _add_generator_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--devices", type=int, default=GeneratorOptions.devices)
    parser.add_argument(
        "--tags-per-device",
        type=int,
        default=GeneratorOptions.tags_per_device,
    )
    parser.add_argument("--tenant-id", default=GeneratorOptions.tenant_id)
    parser.add_argument("--asset-id", default=GeneratorOptions.asset_id)
    parser.add_argument("--agent-id", default=GeneratorOptions.agent_id)
    parser.add_argument("--source-id", default=GeneratorOptions.source_id)
    parser.add_argument("--seed", type=int, default=GeneratorOptions.seed)


def _add_format_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--format",
        choices=("json", "yaml"),
        default="json",
        help="Output format.",
    )


def _add_seed_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--config-registry-url",
        default=os.getenv("CONFIG_REGISTRY_URL", "http://localhost:8000"),
        help="Config Registry base URL.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=30.0,
        help="HTTP request timeout for Config Registry API.",
    )
    parser.add_argument("--config-revision", default=None)
    parser.add_argument("--issued-at", default=None)
    parser.add_argument("--no-reset", action="store_true")
    parser.add_argument("--allow-destructive-reset", action="store_true")
    parser.add_argument("--clickhouse-url", default=os.getenv("CLICKHOUSE_HTTP_URL"))
    parser.add_argument("--mqtt-broker-url", default=os.getenv("MQTT_BROKER"))
    parser.add_argument(
        "--api-concurrency",
        type=int,
        default=4,
        help="Reserved for future async Config Registry clients; current seeder is sync.",
    )


def _add_runtime_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--host", default=os.getenv("KNX_EMULATOR_HOST", "127.0.0.1"))
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("KNX_EMULATOR_PORT", "3671")),
    )
    parser.add_argument(
        "--interval-seconds",
        type=float,
        default=60.0,
        help="Fallback generated-period interval for points missing cadence.",
    )
    parser.add_argument(
        "--time-scale",
        type=float,
        default=60.0,
        help="Replay generated cadence faster for local smoke runs.",
    )
    parser.add_argument(
        "--duration-seconds",
        type=float,
        default=None,
        help="Stop automatically after this duration; omit for long-running mode.",
    )
    parser.add_argument(
        "--log-level",
        default=os.getenv("LOG_LEVEL", "INFO"),
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
    )


def _generator_options(args: argparse.Namespace) -> GeneratorOptions:
    return GeneratorOptions(
        devices=args.devices,
        tags_per_device=args.tags_per_device,
        tenant_id=args.tenant_id,
        asset_id=args.asset_id,
        agent_id=args.agent_id,
        source_id=args.source_id,
        seed=args.seed,
    )


def _seed_config(model, args: argparse.Namespace):
    reset_policy = ResetPolicy(
        enabled=not args.no_reset,
        allow_destructive_reset=args.allow_destructive_reset,
        clickhouse_url=args.clickhouse_url,
        mqtt_broker_url=args.mqtt_broker_url,
    )
    client = ConfigRegistryHttpClient(
        args.config_registry_url,
        timeout_seconds=args.timeout_seconds,
    )
    seeder = ConfigRegistrySeeder(client, reset_policy=reset_policy)
    return seeder.seed(
        model,
        config_registry_url=args.config_registry_url,
        config_revision=args.config_revision,
        issued_at=_parse_issued_at(args.issued_at),
    )


def _run_model(
    model,
    args: argparse.Namespace,
    *,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    del stderr
    emulator_model = build_emulator_model(model)
    options = EmulatorOptions(
        host=args.host,
        port=args.port,
        interval_seconds=args.interval_seconds,
        time_scale=args.time_scale,
        seed=args.seed,
    )
    try:
        _run_with_signals(
            emulator_model,
            options,
            duration_seconds=args.duration_seconds,
            stdout=stdout,
        )
    except KeyboardInterrupt:
        print("event=interrupted", file=stdout)
    return 0


def _run_with_signals(
    emulator_model,
    options: EmulatorOptions,
    *,
    duration_seconds: float | None,
    stdout: TextIO,
) -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    stop = loop.create_future()

    def request_stop() -> None:
        if not stop.done():
            stop.set_result(None)

    for signum in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError, RuntimeError):
            loop.add_signal_handler(signum, request_stop)

    async def run() -> None:
        task = asyncio.create_task(
            run_emulator(
                emulator_model,
                options,
                duration_seconds=duration_seconds,
                stdout=stdout,
            )
        )
        if duration_seconds is None:
            done, pending = await asyncio.wait(
                {task, stop},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for pending_task in pending:
                pending_task.cancel()
            for pending_task in pending:
                with contextlib.suppress(asyncio.CancelledError):
                    await pending_task
            for done_task in done:
                await done_task
        else:
            await task

    try:
        loop.run_until_complete(run())
    finally:
        loop.close()
        asyncio.set_event_loop(None)


def _parse_issued_at(value: str | None) -> datetime | str | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value


def _write_document(value: Any, output_format: str, stdout: TextIO) -> None:
    if output_format == "json":
        json.dump(value, stdout, ensure_ascii=False, indent=2)
        stdout.write("\n")
        return
    stdout.write(_to_yaml(value))


def _to_yaml(value: Any, *, indent: int = 0) -> str:
    prefix = " " * indent
    if isinstance(value, dict):
        lines: list[str] = []
        for key, item in value.items():
            if isinstance(item, dict | list):
                lines.append(f"{prefix}{key}:")
                lines.append(_to_yaml(item, indent=indent + 2).rstrip())
            else:
                lines.append(f"{prefix}{key}: {_scalar_yaml(item)}")
        return "\n".join(lines) + "\n"
    if isinstance(value, list):
        if not value:
            return f"{prefix}[]\n"
        lines = []
        for item in value:
            if isinstance(item, dict | list):
                lines.append(f"{prefix}-")
                lines.append(_to_yaml(item, indent=indent + 2).rstrip())
            else:
                lines.append(f"{prefix}- {_scalar_yaml(item)}")
        return "\n".join(lines) + "\n"
    return f"{prefix}{_scalar_yaml(value)}\n"


def _scalar_yaml(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    text = str(value)
    if re.fullmatch(r"[A-Za-z0-9_.%|/-]+", text):
        return text
    return json.dumps(text, ensure_ascii=False)
