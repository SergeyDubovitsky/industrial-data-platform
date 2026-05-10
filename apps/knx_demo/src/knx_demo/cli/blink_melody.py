from __future__ import annotations

import argparse
import asyncio
import logging

from knx_demo.application.blink_melody import BlinkMelodyCommand, run_blink_melody
from knx_demo.cli.common import add_connection_arguments, profile_from_args
from knx_demo.infrastructure.console import ConsoleLogger
from knx_demo.infrastructure.xknx import XknxBlinkGateway


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Blink a KNX light with a short recognizable rhythm and log feedback."
        )
    )
    add_connection_arguments(
        parser,
        profile_help="Connection preset. 'external' is the default working profile from this workstation.",
    )
    parser.add_argument(
        "--switch-address",
        default="0/0/1",
        help="Group address for switch commands.",
    )
    parser.add_argument(
        "--feedback-address",
        default="0/0/7",
        help="Group address for feedback telegrams.",
    )
    parser.add_argument(
        "--rhythm",
        choices=["sos"],
        default="sos",
        help="Demo rhythm.",
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=3,
        help="How many times to repeat the rhythm.",
    )
    parser.add_argument(
        "--unit",
        type=float,
        default=0.18,
        help="Base rhythm unit in seconds.",
    )
    parser.add_argument(
        "--prepare-off-seconds",
        type=float,
        default=0.5,
        help="Pause after forced OFF before the rhythm starts.",
    )
    parser.add_argument(
        "--finish-off-seconds",
        type=float,
        default=0.8,
        help="Final OFF hold at the end of the demo.",
    )
    parser.add_argument(
        "--max-seconds",
        type=float,
        default=30.0,
        help="Safety limit for total demo duration.",
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
    command = BlinkMelodyCommand(
        profile=profile,
        switch_address=args.switch_address,
        feedback_address=args.feedback_address,
        rhythm=args.rhythm,
        repeats=args.repeats,
        unit=args.unit,
        prepare_off_seconds=args.prepare_off_seconds,
        finish_off_seconds=args.finish_off_seconds,
        max_seconds=args.max_seconds,
    )
    gateway = XknxBlinkGateway(
        profile=profile,
        switch_address=args.switch_address,
        feedback_address=args.feedback_address,
    )
    try:
        await run_blink_melody(command, gateway=gateway, logger=ConsoleLogger())
    except ValueError as error:
        raise SystemExit(str(error)) from error


def main(argv: list[str] | None = None) -> None:
    asyncio.run(run(argv))
