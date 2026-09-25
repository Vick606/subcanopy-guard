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

"""Diagnostic: for a matched attack/benign pair, show where signals differ.

If the attack scores HIGH and the benign scores LOW, and the text of the
attack is benign + injected payload, then the injection itself is what
fired. If attack and benign score the same, the signal isn't looking at
the injection.

Run:
    uv run python -m bench.diagnose
    uv run python -m bench.diagnose --suite banking
"""

from __future__ import annotations

import argparse

from bench.corpus import load
from subcanopy_guard import density, discontinuity
from subcanopy_guard.scanner import ContextScanner


def _show(label: str, text: str, scanner: ContextScanner) -> None:
    result = scanner.scan(text)
    d = density.score(text)
    di = discontinuity.score(text)

    print(f"\n{'=' * 70}")
    print(f"{label}")
    print(f"{'=' * 70}")
    print(f"  text length:      {len(text)} chars")
    print(f"  severity:         {result.severity}")
    print(f"  final risk:       {result.risk:.3f}")
    print(f"  density_risk:     {result.density_risk:.3f}  "
          f"(hotspots: {len(d.hotspots)})")
    print(f"  discontinuity:    {result.discontinuity_risk:.3f}  "
          f"(hotspots: {len(di.hotspots)})")
    print(f"  provenance:       {result.provenance_multiplier:.1f}x")

    print("\n  --- first 500 chars ---")
    print(text[:500])

    print("\n  --- last 500 chars ---")
    print(text[-500:])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--suite",
        default="workspace",
        choices=["workspace", "travel", "banking", "slack"],
    )
    args = parser.parse_args()

    cases = load()
    attack = next(
        c for c in cases if c["label"] == "attack" and c["suite"] == args.suite
    )
    benign = next(
        c for c in cases if c["label"] == "benign" and c["suite"] == args.suite
    )

    # The benign case shares its prefix with the attack. Verify that.
    common_prefix_len = 0
    for a, b in zip(attack["text"], benign["text"], strict=False):
        if a != b:
            break
        common_prefix_len += 1

    print(f"Suite: {args.suite}")
    print(f"Common prefix between attack and benign: {common_prefix_len} chars")
    print(f"Benign length: {len(benign['text'])}")
    print(f"Attack length: {len(attack['text'])}")
    print(f"Injection portion: {len(attack['text']) - common_prefix_len} chars")

    scanner = ContextScanner(source="tool_output")
    _show("BENIGN", benign["text"], scanner)
    _show("ATTACK", attack["text"], scanner)


if __name__ == "__main__":
    main()
