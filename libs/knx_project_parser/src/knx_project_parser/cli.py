from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from knx_project_parser.parser import parse_knxproj


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="knx-project-parser",
        description="Parse ETS .knxproj archives and print a YAML representation.",
    )
    parser.add_argument("project_file", type=Path, help="Path to the .knxproj file")
    parser.add_argument(
        "--password",
        help="Optional ZIP password for encrypted ETS archives",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Deprecated compatibility flag. YAML output is already formatted.",
    )
    return parser


def _dump_yaml(data: object) -> str:
    return yaml.safe_dump(
        data,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    )


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    project = parse_knxproj(args.project_file, password=args.password)
    print(_dump_yaml(project.to_dict()), end="")
