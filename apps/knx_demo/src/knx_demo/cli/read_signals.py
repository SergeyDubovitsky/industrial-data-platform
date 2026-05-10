from __future__ import annotations

import argparse
import asyncio
import logging

from knx_demo.application.read_signals import ReadSignalsCommand, run_read_signals
from knx_demo.cli.common import add_connection_arguments, profile_from_args
from knx_demo.infrastructure.console import ConsoleLogger
from knx_demo.infrastructure.xknx import XknxSignalReaderGateway


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Send GroupValueRead to KNX group addresses and log replies or "
            "passive updates from the bus."
        )
    )
    add_connection_arguments(
        parser,
        profile_help="Connection preset. 'external' matches the NAT route used from this workstation.",
    )
    parser.add_argument(
        "--address",
        action="append",
        default=None,
        help="Group address to read. Repeat the flag for multiple addresses.",
    )
    parser.add_argument(
        "--payload-length",
        type=int,
        default=0,
        help="0 for DPT1/bool, 1+ for raw byte payload length.",
    )
    parser.add_argument(
        "--read-timeout",
        type=float,
        default=2.0,
        help="Seconds to wait for a direct GroupValueRead response per address.",
    )
    parser.add_argument(
        "--monitor-seconds",
        type=float,
        default=5.0,
        help="Extra time to listen for passive write telegrams after sending reads.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Python logging level for xknx internals.",
    )
    return parser.parse_args(argv)


async def run(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logging.getLogger("xknx").setLevel(getattr(logging, args.log_level))

    profile = profile_from_args(args)
    addresses = tuple(args.address or ["0/0/7"])
    command = ReadSignalsCommand(
        profile=profile,
        addresses=addresses,
        payload_length=args.payload_length,
        read_timeout=args.read_timeout,
        monitor_seconds=args.monitor_seconds,
    )
    gateway = XknxSignalReaderGateway(
        profile=profile,
        addresses=addresses,
        payload_length=args.payload_length,
    )
    await run_read_signals(command, gateway=gateway, logger=ConsoleLogger())


def main(argv: list[str] | None = None) -> None:
    asyncio.run(run(argv))
