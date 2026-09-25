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

Usage:
    scg scan tool_output.txt
    scg scan -                       # read from stdin
    cat file.txt | scg scan -
    scg scan --json file.txt
    scg scan --source tool_output --block-at HIGH file.txt

Exit codes:
    0   no findings at or above the block threshold
    1   findings at or above the block threshold
    2   usage or file error
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path

from subcanopy_guard import __version__
from subcanopy_guard.scanner import ContextScanner, ScanResult

_VALID_SOURCES = ("tool_output", "retrieved_doc", "user_input", "system_prompt")
_VALID_SEVERITIES = ("CLEAN", "LOW", "MEDIUM", "HIGH", "CRITICAL")


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

    scan = subparsers.add_parser(
        "scan",
        help="Scan a file or stdin for prompt injection",
    )
    scan.add_argument(
        "path",
        help="Path to file, or '-' to read from stdin",
    )
    scan.add_argument(
        "--source",
        choices=_VALID_SOURCES,
        default="tool_output",
        help="Provenance source tag (default: tool_output)",
    )
    scan.add_argument(
        "--json",
        action="store_true",
        help="Emit structured JSON instead of human-readable output",
    )
    scan.add_argument(
        "--block-at",
        choices=_VALID_SEVERITIES,
        default="HIGH",
        help="Minimum severity that triggers exit code 1 (default: HIGH)",
    )

    return parser


def _read_input(path: str) -> str:
    """Read the scan input from a file path or stdin.

    Raises:
        FileNotFoundError: if path is not '-' and does not exist.
        OSError: for other read failures.
    """
    if path == "-":
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8")


def _print_human(result: ScanResult, path: str) -> None:
    """Print a human-readable scan report."""
    print(f"scg scan: {path}")
    print(f"  severity:    {result.severity}")
    print(f"  risk:        {result.risk:.2f}")
    print(f"  source:      {result.source}")
    print("  signals:")
    print(f"    density:        {result.density_risk:.2f}")
    print(f"    discontinuity:  {result.discontinuity_risk:.2f}")
    print(f"    provenance:     {result.provenance_multiplier:.1f}x")

    if result.matches:
        print("  matches:")
        for m in result.matches:
            print(f"    - {m}")

    if result.hotspots:
        print(f"  hotspots ({len(result.hotspots)}):")
        for start, end in result.hotspots:
            print(f"    [{start}:{end}]")


def _print_json(result: ScanResult, path: str) -> None:
    """Print a structured JSON scan report."""
    payload = {
        "path": path,
        "result": dataclasses.asdict(result),
    }
    print(json.dumps(payload, indent=2))


def _cmd_scan(args: argparse.Namespace) -> int:
    """Execute the scan subcommand. Returns a process exit code."""
    try:
        text = _read_input(args.path)
    except FileNotFoundError:
        print(f"scg scan: file not found: {args.path}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"scg scan: cannot read {args.path}: {exc}", file=sys.stderr)
        return 2

    scanner = ContextScanner(source=args.source)
    result = scanner.scan(text)

    if args.json:
        _print_json(result, args.path)
    else:
        _print_human(result, args.path)

    return 1 if result.is_blocking(args.block_at) else 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "scan":
        return _cmd_scan(args)

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
