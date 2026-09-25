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

"""Generate and cache the AgentDojo benchmark corpus.

Mirrors the loader in vendor/buried-injections/bench/datasets/__init__.py
so our numbers are directly comparable to the published baselines.

On AgentDojo v1 this produces 726 cases:
  629 attack cases  (user task prompt + clean tool output + injected goal)
   97 benign cases  (user task prompt + clean tool output)

Usage:
    uv run python -m bench.corpus           # generate and cache
    uv run python -m bench.corpus --show 2  # show 2 samples of each label
    uv run python -m bench.corpus --regenerate
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

CACHE_PATH = Path(__file__).parent / "corpus_agentdojo.jsonl"
AGENTDOJO_VERSION = "v1"


def generate() -> list[dict[str, str]]:
    """Build the corpus from the agentdojo package.

    Returns a list of dicts with keys: label, suite, text.
    """
    from agentdojo.attacks.important_instructions_attacks import (
        ImportantInstructionsAttack,
    )
    from agentdojo.task_suite.load_suites import get_suites

    template = ImportantInstructionsAttack._JB_STRING
    cases: list[dict[str, str]] = []

    for suite_name, suite in get_suites(AGENTDOJO_VERSION).items():
        outputs = [v for v in suite.get_injection_vector_defaults().values() if v]

        for i, user_task in enumerate(suite.user_tasks.values()):
            tool_output = outputs[i % len(outputs)]
            clean = f"{user_task.PROMPT}\n{tool_output}"
            cases.append(
                {"label": "benign", "suite": suite_name, "text": clean}
            )

            for injection_task in suite.injection_tasks.values():
                payload = template.format(
                    user="Emma Johnson",
                    model="the AI assistant",
                    goal=injection_task.GOAL,
                )
                cases.append(
                    {
                        "label": "attack",
                        "suite": suite_name,
                        "text": clean + payload,
                    }
                )

    return cases


def load() -> list[dict[str, str]]:
    """Load the corpus, generating and caching it if not present."""
    if not CACHE_PATH.exists():
        cases = generate()
        with CACHE_PATH.open("w", encoding="utf-8") as f:
            for case in cases:
                f.write(json.dumps(case) + "\n")
        return cases

    cases: list[dict[str, str]] = []
    with CACHE_PATH.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    return cases


def _summarize(cases: list[dict[str, str]]) -> None:
    attacks = sum(1 for c in cases if c["label"] == "attack")
    benign = sum(1 for c in cases if c["label"] == "benign")
    suites = sorted({c["suite"] for c in cases})
    print(f"Total:  {len(cases)} cases (attacks={attacks}, benign={benign})")
    print(f"Suites: {', '.join(suites)}")
    print(f"Cache:  {CACHE_PATH}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate and cache the AgentDojo benchmark corpus."
    )
    parser.add_argument(
        "--show",
        type=int,
        default=1,
        help="Show N samples of each label (default: 1, use 0 to skip)",
    )
    parser.add_argument(
        "--regenerate",
        action="store_true",
        help="Force regeneration even if cache exists",
    )
    args = parser.parse_args()

    if args.regenerate and CACHE_PATH.exists():
        CACHE_PATH.unlink()

    cases = load()
    _summarize(cases)

    if args.show > 0:
        for label in ("attack", "benign"):
            samples = [c for c in cases if c["label"] == label][: args.show]
            for i, s in enumerate(samples, 1):
                print(f"--- {label.upper()} sample {i} ({s['suite']}) ---")
                text = s["text"]
                print(text[:700] + ("..." if len(text) > 700 else ""))
                print()


if __name__ == "__main__":
    main()
