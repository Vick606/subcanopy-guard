"""Quick stats on the PromptWall dataset."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

DATA = Path(__file__).parent.parent / "vendor" / "promptwall"


def load_jsonl(path: Path) -> list[dict]:
    records = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def main() -> None:
    attacks = load_jsonl(DATA / "attacks.jsonl")
    safe = load_jsonl(DATA / "safe.jsonl")

    print(f"Total attacks: {len(attacks)}")
    print(f"Total safe:    {len(safe)}")
    print()
    print("Attack types:")
    for atype, count in Counter(a["attack_type"] for a in attacks).most_common():
        print(f"  {atype:<25} {count}")

    print()
    avg_attack = sum(len(a["prompt"]) for a in attacks) // len(attacks)
    avg_safe = sum(len(s["prompt"]) for s in safe) // len(safe)
    print(f"Average attack length: {avg_attack} chars")
    print(f"Average safe length:   {avg_safe} chars")


if __name__ == "__main__":
    main()
