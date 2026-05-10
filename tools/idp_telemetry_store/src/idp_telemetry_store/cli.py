from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path
from typing import Sequence

from idp_telemetry_store.http_client import ClickHouseSettings, HttpClickHouseClient
from idp_telemetry_store.load_poc import (
    TelemetryReadModelLoadPocConfig,
    result_to_json,
    run_telemetry_read_model_load_poc,
)
from idp_telemetry_store.migrations import (
    MigrationError,
    apply_pending_migrations,
    migration_statuses,
)


def main(argv: Sequence[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    client = HttpClickHouseClient(ClickHouseSettings.from_env())

    try:
        if args.command == "migrate" and args.action == "status":
            migrations_dir = _resolve_migrations_dir(args.migrations_dir)
            statuses = migration_statuses(client, migrations_dir)
            _print_statuses(statuses)
        elif args.command == "migrate" and args.action == "up":
            migrations_dir = _resolve_migrations_dir(args.migrations_dir)
            applied = apply_pending_migrations(client, migrations_dir)
            if not applied:
                print("No pending migrations.")
            else:
                for migration in applied:
                    print(f"Applied {migration.version}")
        elif args.command == "load-poc" and args.target == "telemetry-read-models":
            result = run_telemetry_read_model_load_poc(
                client,
                TelemetryReadModelLoadPocConfig(
                    rows=args.rows,
                    points=args.points,
                    batch_size=args.batch_size,
                    duplicate_every=args.duplicate_every,
                    run_id=args.run_id,
                    start_ts=_parse_utc_datetime(args.start_ts),
                ),
            )
            print(result_to_json(result))
        else:
            parser.error("Unknown command")
    except (MigrationError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="idp-telemetry-store")
    parser.add_argument(
        "--migrations-dir",
        type=Path,
        default=None,
        help="Directory with forward-only ClickHouse SQL migrations.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)
    migrate = subparsers.add_parser("migrate")
    migrate.add_argument("action", choices=["status", "up"])

    load_poc = subparsers.add_parser(
        "load-poc",
        help="Run synthetic ClickHouse load PoCs against local Telemetry Store tables.",
    )
    load_poc.add_argument("target", choices=["telemetry-read-models"])
    load_poc.add_argument("--rows", type=int, default=50_000)
    load_poc.add_argument("--points", type=int, default=100)
    load_poc.add_argument("--batch-size", type=int, default=10_000)
    load_poc.add_argument(
        "--duplicate-every",
        type=int,
        default=10,
        help="Insert one replay duplicate after every N logical rows; use 0 to disable.",
    )
    load_poc.add_argument(
        "--run-id",
        default=None,
        help="Optional run id used in tenant/asset ids. Defaults to current UTC timestamp.",
    )
    load_poc.add_argument(
        "--start-ts",
        default="2026-05-03T00:00:00Z",
        help="UTC start timestamp for generated telemetry rows.",
    )
    return parser


def _resolve_migrations_dir(path: Path | None) -> Path:
    if path is not None:
        return path

    package_root = Path(__file__).resolve().parents[2]
    package_migrations = package_root / "migrations"
    if package_migrations.exists():
        return package_migrations

    cwd = Path.cwd()
    for candidate_root in (cwd, *cwd.parents):
        candidates = (
            candidate_root / "tools" / "idp_telemetry_store" / "migrations",
            candidate_root / "migrations",
        )
        for candidate in candidates:
            if candidate.exists():
                return candidate
    return package_migrations


def _print_statuses(statuses: object) -> None:
    for status in statuses:
        print(f"{status.state:17} {status.version}")


def _parse_utc_datetime(value: str) -> datetime:
    normalized = value.removesuffix("Z") + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
