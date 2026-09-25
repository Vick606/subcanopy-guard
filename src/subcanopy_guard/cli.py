# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Victor
#
# This file is part of Subcanopy Guard.
#
# Subcanopy Guard is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Commercial licensing is available for organizations that cannot comply
# with the AGPL. See COMMERCIAL_LICENSE.md.

"""Command-line entry point for scg.

Stage 0 provides argument parsing and the scan subcommand stub.
"""

from __future__ import annotations

import argparse
import sys

from subcanopy_guard import __version__


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser."""
    parser = argparse.ArgumentParser(
        prog="scg",
        description="Subcanopy Guard - context-aware indirect prompt injection scanner",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"scg {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser(
        "scan",
        help="Scan a file or stdin (not yet implemented)",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "scan":
        print("scg scan: not yet implemented (Stage 5)", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
