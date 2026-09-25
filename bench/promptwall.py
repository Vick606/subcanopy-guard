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

"""PromptWall generalization benchmark.

The PromptWall dataset (cyberec/promptwall-injection-dataset) contains
430 attacks across 8 categories plus 70 safe prompts for false-positive
testing. Unlike AgentDojo v1, PromptWall uses many different templates
and attack families. This is a generalization test: does the scanner
hold up on data it was never tuned on?

Usage:
    uv run python -m bench.promptwall
    uv run python -m bench.promptwall --block-at HIGH --per-category
    uv run python -m bench.promptwall --show-misses 3
"""

from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from pathlib import Path

from subcanopy_guard.scanner import ContextScanner

DATA_DIR = Path(__file__).parent.parent / "vendor" / "promptwall"


def _load_jsonl(path: Path) -> list[dict]:
    records = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def load() -> tuple[list[dict], list[dict]]:
    """Return (attacks, safe). Each is a list of dicts with 'prompt' and 'attack_type'."""
    attacks = _load_jsonl(DATA_DIR / "attacks.jsonl")
    safe = _load_jsonl(DATA_DIR / "safe.jsonl")
    return attacks, safe


def _p50(values: list[float]) -> float:
    if not values:
        return 0.0
    values.sort()
    return values[len(values) // 2]


def run(
    block_at: str,
    source: str,
    per_category: bool,
    show_misses: int,
) -> dict:
    attacks, safe = load()
    scanner = ContextScanner(source=source)

    caught_by_type: dict[str, int] = defaultdict(int)
    total_by_type: dict[str, int] = defaultdict(int)
    times: list[float] = []
    misses: list[dict] = []

    total_caught = 0
    for a in attacks:
        atype = a["attack_type"]
        total_by_type[atype] += 1

        start = time.perf_counter()
        result = scanner.scan(a["prompt"])
        times.append((time.perf_counter() - start) * 1000.0)

        if result.is_blocking(block_at):
            caught_by_type[atype] += 1
            total_caught += 1
        elif len(misses) < show_misses:
            misses.append(
                {
                    "attack_type": atype,
                    "severity": result.severity,
                    "risk": round(result.risk, 4),
                    "density": round(result.density_risk, 4),
                    "discontinuity": round(result.discontinuity_risk, 4),
                    "prompt": a["prompt"][:200],
                }
            )

    false_blocks = 0
    for s in safe:
        start = time.perf_counter()
        result = scanner.scan(s["prompt"])
        times.append((time.perf_counter() - start) * 1000.0)
        if result.is_blocking(block_at):
            false_blocks += 1

    row = {
        "detector": "subcanopy-guard",
        "block_at": block_at,
        "source": source,
        "attacks_total": len(attacks),
        "attacks_caught": total_caught,
        "detection_rate": total_caught / len(attacks) if attacks else 0.0,
        "safe_total": len(safe),
        "false_blocks": false_blocks,
        "false_positive_rate": false_blocks / len(safe) if safe else 0.0,
        "p50_ms": round(_p50(times), 3),
    }

    if per_category:
        row["by_category"] = {
            t: {
                "caught": caught_by_type[t],
                "total": total_by_type[t],
                "rate": caught_by_type[t] / total_by_type[t],
            }
            for t in sorted(total_by_type)
        }

    if show_misses:
        row["_misses"] = misses

    return row


def _print_summary(row: dict) -> None:
    print()
    print(f"Detector:   {row['detector']}")
    print(f"Source:     {row['source']}")
    print(f"Block at:   {row['block_at']}")
    print()
    print(
        f"  Caught:     {row['attacks_caught']}/{row['attacks_total']}"
        f"  ({row['detection_rate']:.1%})"
    )
    print(
        f"  False pos:  {row['false_blocks']}/{row['safe_total']}"
        f"  ({row['false_positive_rate']:.1%})"
    )
    print(f"  p50:        {row['p50_ms']} ms")


def _print_by_category(row: dict) -> None:
    by_cat = row.get("by_category")
    if not by_cat:
        return
    print()
    print(f"  {'category':<25} {'caught':<12} {'rate':<8}")
    print(f"  {'-' * 45}")
    for cat, stats in by_cat.items():
        print(
            f"  {cat:<25} {stats['caught']}/{stats['total']:<8} "
            f"{stats['rate']:.1%}"
        )


def _print_misses(misses: list[dict]) -> None:
    if not misses:
        return
    print("\nSample misses:")
    for i, m in enumerate(misses, 1):
        print(
            f"\n  [{i}] {m['attack_type']}  severity={m['severity']}  "
            f"risk={m['risk']}  density={m['density']}  "
            f"discontinuity={m['discontinuity']}"
        )
        print(f"      {m['prompt']}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Subcanopy Guard against the PromptWall dataset."
    )
    parser.add_argument(
        "--block-at",
        default="HIGH",
        choices=["CLEAN", "LOW", "MEDIUM", "HIGH", "CRITICAL"],
    )
    parser.add_argument(
        "--source",
        default="user_input",
        choices=["tool_output", "retrieved_doc", "user_input", "system_prompt"],
        help="PromptWall prompts are direct user inputs, so user_input is the default",
    )
    parser.add_argument(
        "--per-category",
        action="store_true",
        help="Print per-category recall breakdown",
    )
    parser.add_argument(
        "--show-misses",
        type=int,
        default=0,
        help="Print N sample misses",
    )
    args = parser.parse_args()

    row = run(args.block_at, args.source, args.per_category, args.show_misses)
    _print_summary(row)
    _print_by_category(row)

    misses = row.pop("_misses", None)
    if misses:
        _print_misses(misses)


if __name__ == "__main__":
    main()
