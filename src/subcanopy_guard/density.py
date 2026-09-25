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

"""Sliding-window instruction density scoring.

This module is the core detection mechanism of Subcanopy Guard. It measures
the local concentration of imperative verbs in a text using a sliding
window over the token stream. Unlike whole-sequence classifiers, this
approach is structurally immune to context dilution: an injection buried
in 500 tokens of benign JSON still produces a localized density spike that
the window catches.

The scoring is weighted. Verbs that are highly diagnostic of prompt
injection ("ignore", "disregard", "jailbreak") count more than common
imperatives ("print", "show", "run"). The window score is normalized by
a fixed target count rather than by window size, so a short injection
in a large window still scores high.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Imperative verb lexicon
# ---------------------------------------------------------------------------
# STRONG verbs are highly diagnostic of prompt injection. They rarely
# appear in benign tool output and are common in injections.
#
# REGULAR verbs are imperatives that appear in instructions generally.
# They contribute signal but less than STRONG verbs.

_STRONG_VERBS: frozenset[str] = frozenset(
    {
        "ignore",
        "disregard",
        "forget",
        "override",
        "bypass",
        "pretend",
        "impersonate",
        "jailbreak",
        "unrestricted",
        "unfiltered",
        "unlock",
        "disclose",
        "leak",
        "exfiltrate",
        "smuggle",
    }
)

_REGULAR_VERBS: frozenset[str] = frozenset(
    {
        # Output forcing
        "print",
        "output",
        "say",
        "repeat",
        "reveal",
        "expose",
        "show",
        "display",
        "dump",
        "echo",
        "respond",
        "answer",
        "write",
        "state",
        # Execution / tool use
        "execute",
        "run",
        "call",
        "invoke",
        "launch",
        "start",
        "stop",
        "kill",
        "delete",
        "remove",
        "drop",
        "send",
        "post",
        "upload",
        "download",
        "fetch",
        "retrieve",
        # Instruction injection markers
        "instruct",
        "command",
        "direct",
        "tell",
        "ask",
        "require",
        "must",
        "should",
        "shall",
        "need",
        # Role reassignment
        "act",
        "behave",
        "roleplay",
        "simulate",
        "emulate",
        "become",
        # Jailbreak-adjacent
        "enable",
        "disable",
    }
)

_IMPERATIVE_VERBS: frozenset[str] = _STRONG_VERBS | _REGULAR_VERBS

_STRONG_WEIGHT = 1.0
_REGULAR_WEIGHT = 0.5

# Pre-compiled regex for the diagnostic `matches()` helper.
_IMPERATIVE_RE = re.compile(
    r"\b(" + "|".join(re.escape(v) for v in sorted(_IMPERATIVE_VERBS)) + r")\b",
    re.IGNORECASE,
)

# Tokenization: word characters or single punctuation marks.
_TOKEN_RE = re.compile(r"\w+|[^\w\s]", re.UNICODE)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class DensityConfig:
    """Configuration for the density scorer.

    The defaults are tuned so that a 10-token injection buried in a
    500-token benign document is caught with a single window.
    """

    window_tokens: int = 25
    """Number of tokens per window."""

    stride_tokens: int = 10
    """How far the window advances between measurements."""

    target_count: float = 2.0
    """Weighted imperative count that maps to a risk of 1.0."""

    hotspot_threshold: float = 0.5
    """Windows scoring at or above this value are reported as hotspots."""

    min_tokens_for_scoring: int = 5
    """Inputs with fewer tokens than this are scored 0.0 (too short to judge)."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@dataclass
class DensityResult:
    """Result of a density scan."""

    risk: float
    """Normalized risk score in [0.0, 1.0]."""

    hotspots: list[tuple[int, int]] = field(default_factory=list)
    """Character-offset ranges (start, end) of windows exceeding the threshold."""

    window_scores: list[float] = field(default_factory=list)
    """Per-window scores, for diagnostics."""


def _tokenize(text: str) -> list[tuple[str, int, int]]:
    """Tokenize text into (token, start, end) triples.

    Tokens are word characters or punctuation. Whitespace is skipped.
    Character offsets are relative to the original string.
    """
    return [
        (m.group(0), m.start(), m.end())
        for m in _TOKEN_RE.finditer(text)
    ]


def _window_density(tokens: list[tuple[str, int, int]]) -> float:
    """Unweighted density: imperatives divided by token count.

    This is a diagnostic helper. It is not used in scoring.
    """
    if not tokens:
        return 0.0
    hits = sum(1 for tok, _, _ in tokens if tok.lower() in _IMPERATIVE_VERBS)
    return hits / len(tokens)


def _token_weight(tok: str) -> float:
    """Weight for a single token.

    Returns 1.0 for STRONG verbs, 0.5 for REGULAR verbs, 0.0 otherwise.
    """
    low = tok.lower()
    if low in _STRONG_VERBS:
        return _STRONG_WEIGHT
    if low in _REGULAR_VERBS:
        return _REGULAR_WEIGHT
    return 0.0


def score(
    text: str,
    config: DensityConfig | None = None,
) -> DensityResult:
    """Score text for sliding-window instruction density.

    Args:
        text: The input text to scan.
        config: Optional configuration override.

    Returns:
        A DensityResult with risk score, hotspots, and per-window scores.
    """
    cfg = config or DensityConfig()
    tokens = _tokenize(text)

    if len(tokens) < cfg.min_tokens_for_scoring:
        return DensityResult(risk=0.0)

    # Pre-compute per-token weights once. This avoids repeated set
    # lookups in the hot loop and lets us use C-level sum() over slices.
    weights = [_token_weight(tok) for tok, _, _ in tokens]

    window_scores: list[float] = []
    hotspots: list[tuple[int, int]] = []

    w = cfg.window_tokens
    s = cfg.stride_tokens
    n = len(tokens)

    i = 0
    while i < n:
        end = min(i + w, n)
        weighted = sum(weights[i:end])
        window_score = min(weighted / cfg.target_count, 1.0)
        window_scores.append(window_score)

        if window_score >= cfg.hotspot_threshold:
            hotspots.append((tokens[i][1], tokens[end - 1][2]))

        if i + w >= n:
            break
        i += s

    risk = max(window_scores) if window_scores else 0.0

    return DensityResult(
        risk=risk,
        hotspots=hotspots,
        window_scores=window_scores,
    )


def matches(text: str) -> list[str]:
    """Return the imperative verbs found in text, for diagnostics."""
    return [m.group(0).lower() for m in _IMPERATIVE_RE.finditer(text)]
