from __future__ import annotations

import argparse

from knx_demo.domain.profiles import (
    DEFAULT_PROFILE_NAMES,
    EndpointProfile,
    resolve_endpoint_profile,
)


def add_connection_arguments(parser: argparse.ArgumentParser, profile_help: str) -> None:
    parser.add_argument(
        "--profile",
        choices=sorted(DEFAULT_PROFILE_NAMES),
        default="external",
        help=profile_help,
    )
    parser.add_argument("--gateway-ip", help="Override gateway IP from the selected profile.")
    parser.add_argument(
        "--gateway-port",
        type=int,
        help="Override gateway port from the selected profile.",
    )
    parser.add_argument(
        "--route-back",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Override KNX/IP tunneling route_back flag.",
    )


def profile_from_args(args: argparse.Namespace) -> EndpointProfile:
    return resolve_endpoint_profile(
        profile_name=args.profile,
        gateway_ip=args.gateway_ip,
        gateway_port=args.gateway_port,
        route_back=args.route_back,
    )
