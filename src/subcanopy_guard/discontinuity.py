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

"""Stylometric discontinuity scoring.

Detects abrupt style breaks between adjacent sentences/fragments. An
injection payload typically shifts the writing style from the surrounding
tool output: JSON is terse and declarative, an injection is imperative
and second-person.

The signal is the ADJACENT-SENTENCE delta, not the absolute style. A
sentence with high second-person density is not suspicious on its own
(it could be a docstring), but a sudden transition from zero to high
second-person density is.

This module is inspired by the "stylometric discontinuity" technique
described in the April 2026 paper "Beyond Pattern Matching", which
reported +11.1 F1 points on indirect-injection benchmarks when combined
with density-based detectors.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Feature lexicons
# ---------------------------------------------------------------------------

# Second-person pronouns. These are strong indicators of an instruction
# directed at the model ("you must", "your system prompt").
_SECOND_PERSON_WORDS: frozenset[str] = frozenset(
    {
        "you",
        "your",
        "yours",
        "yourself",
        "yourselves",
    }
)

# Imperative verbs relevant to prompt injection. A subset of the density
# module's lexicon, focused on verbs that indicate an instruction to the
# model rather than generic actions.
_IMPERATIVE_VERBS: frozenset[str] = frozenset(
    {
        # Override / disregard
        "ignore",
        "disregard",
        "forget",
        "override",
        "bypass",
        "skip",
        # Output forcing
        "print",
        "output",
        "reveal",
        "disclose",
        "expose",
        "leak",
        "show",
        "display",
        "dump",
        "echo",
        # Execution
        "execute",
        "run",
        "invoke",
        "call",
        "launch",
        # Persona reassignment
        "act",
        "pretend",
        "roleplay",
        "impersonate",
        "simulate",
        "become",
        # Instruction markers
        "instruct",
        "command",
        "direct",
        "require",
        # Modal obligation
        "must",
        "should",
        "shall",
        # Explicit commands
        "tell",
        "ask",
        "send",
        "delete",
        "remove",
    }
)

# Sentence/fragment boundaries. We split on whitespace that follows
# sentence-ending punctuation, JSON structural characters, or commas.
# This handles both prose and JSON tool output.
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?,;}\]])\s+|\n+")

# Word tokenization: captures only word characters (letters, digits, _).
# Punctuation is ignored for feature extraction.
_WORD_RE = re.compile(r"\w+", re.UNICODE)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class DiscontinuityConfig:
    """Configuration for the discontinuity scorer.

    The defaults are tuned so that a clean JSON tool output scores near
    zero, while a JSON output with a buried English injection scores
    above 0.6.
    """

    baseline_delta: float = 0.1
    """Deltas at or below this value are treated as natural variation."""

    scale: float = 0.3
    """Deltas above ``baseline_delta + scale`` saturate risk at 1.0."""

    hotspot_delta_threshold: float = 0.2
    """Raw deltas above this value are reported as hotspots."""

    min_sentences: int = 3
    """Inputs with fewer than this many sentences are scored 0.0."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@dataclass
class DiscontinuityResult:
    """Result of a discontinuity scan."""

    risk: float
    """Normalized risk score in [0.0, 1.0]."""

    available: bool = True
    """True if there were enough sentences to compute a delta. False otherwise."""

    hotspots: list[tuple[int, int]] = field(default_factory=list)
    """Character-offset ranges (start, end) around high-delta sentence pairs."""

    window_scores: list[float] = field(default_factory=list)
    """Per-pair delta values, for diagnostics."""


def _split_sentences(text: str) -> list[tuple[str, int, int]]:
    """Split text into sentences/fragments.

    Returns a list of ``(text, start, end)`` triples. Boundaries are
    whitespace that follows sentence-ending punctuation, JSON structural
    characters, or commas. This handles prose, JSON, and mixed content.
    """
    results: list[tuple[str, int, int]] = []
    last_end = 0

    for match in _SENTENCE_SPLIT_RE.finditer(text):
        if match.start() > last_end:
            fragment = text[last_end : match.start()]
            if fragment.strip():
                results.append((fragment, last_end, match.start()))
        last_end = match.end()

    if last_end < len(text):
        fragment = text[last_end:]
        if fragment.strip():
            results.append((fragment, last_end, len(text)))

    return results


def _sentence_features(text: str) -> tuple[float, float]:
    """Extract (second_person_density, imperative_density) from a sentence.

    Both values are in ``[0.0, 1.0]``. A density is the fraction of word
    tokens in the sentence that belong to the corresponding lexicon.
    """
    words = _WORD_RE.findall(text)
    if not words:
        return (0.0, 0.0)

    n = len(words)
    lower = [w.lower() for w in words]

    second_person = sum(1 for w in lower if w in _SECOND_PERSON_WORDS)
    imperatives = sum(1 for w in lower if w in _IMPERATIVE_VERBS)

    return (second_person / n, imperatives / n)


def _delta(
    a: tuple[float, float],
    b: tuple[float, float],
) -> float:
    """L1 distance between two feature vectors."""
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def score(
    text: str,
    config: DiscontinuityConfig | None = None,
) -> DiscontinuityResult:
    """Score text for stylometric discontinuity between adjacent sentences.

    Args:
        text: The input text to scan.
        config: Optional configuration override.

    Returns:
        A DiscontinuityResult with risk score, hotspots, and per-pair deltas.
    """
    cfg = config or DiscontinuityConfig()
    sentences = _split_sentences(text)

    if len(sentences) < cfg.min_sentences:
        return DiscontinuityResult(risk=0.0, available=False)

    features = [_sentence_features(s[0]) for s in sentences]

    deltas: list[float] = []
    hotspots: list[tuple[int, int]] = []

    for i in range(1, len(sentences)):
        delta = _delta(features[i - 1], features[i])
        deltas.append(delta)

        if delta >= cfg.hotspot_delta_threshold:
            # Hotspot spans the end of the previous sentence and the end
            # of the current sentence, so callers can see the transition.
            start = sentences[i - 1][1]
            end = sentences[i][2]
            hotspots.append((start, end))

    max_delta = max(deltas) if deltas else 0.0

    if max_delta <= cfg.baseline_delta:
        risk = 0.0
    else:
        risk = min((max_delta - cfg.baseline_delta) / cfg.scale, 1.0)

    return DiscontinuityResult(
        risk=risk,
        available=True,
        hotspots=hotspots,
        window_scores=deltas,
    )
