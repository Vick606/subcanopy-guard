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

"""Run Subcanopy Guard against the buried-injections AgentDojo corpus.

Mirrors the metric computed by vendor/buried-injections/bench/run.py so
our numbers are directly comparable to the published baselines:

    attacks_caught / attacks_total
    false_blocks / benign_total
    median latency per scan

Usage:
    uv run python -m bench.run
    uv run python -m bench.run --block-at HIGH
    uv run python -m bench.run --source tool_output
    uv run python -m bench.run --show-misses 5
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from bench.corpus import load
from subcanopy_guard.scanner import ContextScanner

RESULTS_PATH = Path(__file__).parent / "results_scg.json"


def _p50(values: list[float]) -> float:
    if not values:
        return 0.0
    values.sort()
    return values[len(values) // 2]


def run(
    block_at: str,
    source: str,
    show_misses: int = 0,
) -> dict:
    """Run the scanner over the corpus and return the metrics row."""
    cases = load()
    attacks = [c for c in cases if c["label"] == "attack"]
    benign = [c for c in cases if c["label"] == "benign"]

    scanner = ContextScanner(source=source)

    caught = 0
    false_blocks = 0
    attack_times: list[float] = []
    benign_times: list[float] = []
    misses: list[dict] = []

    for c in attacks:
        start = time.perf_counter()
        result = scanner.scan(c["text"])
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        attack_times.append(elapsed_ms)

        if result.is_blocking(block_at):
            caught += 1
        elif len(misses) < show_misses:
            misses.append(
                {
                    "suite": c["suite"],
                    "severity": result.severity,
                    "risk": round(result.risk, 4),
                    "density": round(result.density_risk, 4),
                    "discontinuity": round(result.discontinuity_risk, 4),
                    "preview": c["text"][-200:],
                }
            )

    for c in benign:
        start = time.perf_counter()
        result = scanner.scan(c["text"])
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        benign_times.append(elapsed_ms)

        if result.is_blocking(block_at):
            false_blocks += 1

    all_times = attack_times + benign_times

    row = {
        "detector": "subcanopy-guard",
        "block_at": block_at,
        "source": source,
        "attacks_total": len(attacks),
        "attacks_caught": caught,
        "detection_rate": caught / len(attacks) if attacks else 0.0,
        "benign_total": len(benign),
        "false_blocks": false_blocks,
        "false_positive_rate": false_blocks / len(benign) if benign else 0.0,
        "p50_ms": round(_p50(all_times), 3),
        "p50_attack_ms": round(_p50(attack_times), 3),
        "p50_benign_ms": round(_p50(benign_times), 3),
    }

    if show_misses:
        row["_misses"] = misses

    return row


def _print_row(row: dict) -> None:
    print(f"\nDetector:    {row['detector']}")
    print(f"Source:      {row['source']}")
    print(f"Block at:    {row['block_at']}")
    print()
    print(
        f"  Caught:      {row['attacks_caught']}/{row['attacks_total']}"
        f"  ({row['detection_rate']:.1%})"
    )
    print(
        f"  False pos:   {row['false_blocks']}/{row['benign_total']}"
        f"  ({row['false_positive_rate']:.1%})"
    )
    print(f"  p50:         {row['p50_ms']} ms")
    print(f"  p50 attack:  {row['p50_attack_ms']} ms")
    print(f"  p50 benign:  {row['p50_benign_ms']} ms")


def _print_misses(misses: list[dict]) -> None:
    if not misses:
        return
    print("\nSample misses (attacks that scored below blocking):")
    for i, m in enumerate(misses, 1):
        print(f"\n  [{i}] suite={m['suite']}  severity={m['severity']}  "
              f"risk={m['risk']}  density={m['density']}  "
              f"discontinuity={m['discontinuity']}")
        print(f"      tail: ...{m['preview'].replace(chr(10), ' | ')}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Subcanopy Guard against the AgentDojo corpus."
    )
    parser.add_argument(
        "--block-at",
        default="HIGH",
        choices=["CLEAN", "LOW", "MEDIUM", "HIGH", "CRITICAL"],
        help="Minimum severity that counts as a detection (default: HIGH)",
    )
    parser.add_argument(
        "--source",
        default="tool_output",
        choices=["tool_output", "retrieved_doc", "user_input", "system_prompt"],
        help="Provenance source used for the scan (default: tool_output)",
    )
    parser.add_argument(
        "--show-misses",
        type=int,
        default=0,
        help="Print N sample attacks that were missed (default: 0)",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help=f"Write the result row to {RESULTS_PATH.name}",
    )
    args = parser.parse_args()

    row = run(args.block_at, args.source, args.show_misses)
    _print_row(row)

    misses = row.pop("_misses", None)
    if misses:
        _print_misses(misses)

    if args.save:
        RESULTS_PATH.write_text(json.dumps(row, indent=2), encoding="utf-8")
        print(f"\nSaved: {RESULTS_PATH}")


if __name__ == "__main__":
    main()
