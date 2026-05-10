from __future__ import annotations

import argparse

from knx_demo.cli import blink_melody, read_signals


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="knx-demo",
        description="KNX demo utilities for bus reads and blink sequences.",
    )
    subparsers = parser.add_subparsers(dest="command")
    subparsers.required = True

    read_parser = subparsers.add_parser(
        "read-signals",
        help="Send GroupValueRead requests and log replies or passive updates.",
    )
    read_parser.set_defaults(handler=read_signals.main)

    blink_parser = subparsers.add_parser(
        "blink-melody",
        help="Blink a KNX light with a recognizable rhythm and log feedback.",
    )
    blink_parser.set_defaults(handler=blink_melody.main)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    namespace, remaining = parser.parse_known_args(argv)
    handler = namespace.handler
    handler(remaining)
