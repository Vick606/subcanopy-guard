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

"""Public scanner API.

This module composes the three detection signals (density, discontinuity,
provenance) into a single ContextScanner that returns a structured
ScanResult and optionally raises InjectionRiskError via the protect()
decorator.

Combination strategy:
1. Combine density and discontinuity, honoring signal availability.
   A signal that cannot be computed (input too short) does NOT dilute
   the available signal with a phantom zero. If both are available, use
   a weighted sum with an agreement bonus; if only one is available,
   use it directly; if neither is available, the combined risk is 0.0.
2. Provenance multiplier applied after combination.
3. Severity classification from the final adjusted risk.

References:
- ASCEND severity model (critical/high/medium/low/info)
- tester311249/llm-security threat levels (SAFE/LOW/MEDIUM/HIGH/CRITICAL)
- LLM Guard scanner composition pattern
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

from subcanopy_guard import density, discontinuity, provenance
from subcanopy_guard.exceptions import InjectionRiskError

# ---------------------------------------------------------------------------
# Default weights and thresholds
# ---------------------------------------------------------------------------

_DENSITY_WEIGHT = 0.6
_DISCONTINUITY_WEIGHT = 0.4
_AGREEMENT_THRESHOLD = 0.3
_AGREEMENT_BONUS = 1.15

# Severity boundaries. Based on ASCEND and llm-security conventions,
# mapped to a normalized [0.0, 1.0] risk scale.
_SEVERITY_BANDS: tuple[tuple[float, str], ...] = (
    (0.75, "CRITICAL"),
    (0.55, "HIGH"),
    (0.35, "MEDIUM"),
    (0.15, "LOW"),
    (0.0, "CLEAN"),
)

_T = TypeVar("_T")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class ScannerConfig:
    """Configuration for the ContextScanner."""

    density_weight: float = _DENSITY_WEIGHT
    """Weight of the density signal in the combined risk."""

    discontinuity_weight: float = _DISCONTINUITY_WEIGHT
    """Weight of the discontinuity signal in the combined risk."""

    agreement_threshold: float = _AGREEMENT_THRESHOLD
    """Both signals must exceed this value to trigger the agreement bonus."""

    agreement_bonus: float = _AGREEMENT_BONUS
    """Multiplier applied to the combined risk when both signals agree."""

    block_severity: str = "HIGH"
    """Minimum severity at which protect() raises InjectionRiskError."""


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class ScanResult:
    """Structured result of a scan."""

    severity: str
    """One of CLEAN, LOW, MEDIUM, HIGH, CRITICAL."""

    risk: float
    """Final adjusted risk score in [0.0, 1.0]."""

    source: str
    """The provenance source tag used for adjustment."""

    density_risk: float = 0.0
    """Raw density signal contribution before weighting."""

    discontinuity_risk: float = 0.0
    """Raw discontinuity signal contribution before weighting."""

    provenance_multiplier: float = 1.0
    """Multiplier applied by the provenance stage."""

    matches: list[str] = field(default_factory=list)
    """Human-readable labels of the signals that fired."""

    hotspots: list[tuple[int, int]] = field(default_factory=list)
    """Character-offset ranges of suspicious regions."""

    def is_blocking(self, threshold: str = "HIGH") -> bool:
        """Return True if severity is at or above the given threshold."""
        order = {"CLEAN": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
        return order.get(self.severity, 0) >= order.get(threshold, 3)


# ---------------------------------------------------------------------------
# Severity classification
# ---------------------------------------------------------------------------

def classify(risk: float) -> str:
    """Map a normalized risk score to a severity label."""
    for boundary, label in _SEVERITY_BANDS:
        if risk >= boundary:
            return label
    return "CLEAN"


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------

class ContextScanner:
    """Context-aware indirect prompt injection scanner.

    Composes density, discontinuity, and provenance signals into a single
    scan. The scanner is stateless and reentrant; create one per source
    type or share across calls.
    """

    def __init__(
        self,
        source: str = "user_input",
        config: ScannerConfig | None = None,
        density_config: density.DensityConfig | None = None,
        discontinuity_config: discontinuity.DiscontinuityConfig | None = None,
        provenance_config: provenance.ProvenanceConfig | None = None,
    ) -> None:
        self.source = source
        self.config = config or ScannerConfig()
        self._density_config = density_config
        self._discontinuity_config = discontinuity_config
        self._provenance_config = provenance_config

    def scan(self, text: str, source: str | None = None) -> ScanResult:
        """Scan text and return a structured ScanResult.

        Args:
            text: The input text to scan.
            source: Optional override for the provenance source tag. If
                omitted, the scanner's configured source is used.

        Returns:
            A ScanResult with severity, risk, contributions, and hotspots.
        """
        effective_source = source or self.source

        # Stage 1: density
        density_result = density.score(text, self._density_config)
        d_risk = density_result.risk

        # Stage 2: discontinuity
        disc_result = discontinuity.score(text, self._discontinuity_config)
        i_risk = disc_result.risk

        # Stage 3: combine signals, honoring availability.
        #
        # If a signal is not available (input too short to compute it), we
        # do NOT dilute the available signal with a phantom zero. A signal
        # that cannot be computed should not vote against a signal that can.
        # This matters for short single-sentence injections (the majority
        # of direct-injection and jailbreak attacks in PromptWall), where
        # discontinuity has no adjacent sentences to compare.
        d_available = density_result.available
        i_available = disc_result.available

        if d_available and i_available:
            base = (
                self.config.density_weight * d_risk
                + self.config.discontinuity_weight * i_risk
            )
            both_fired = (
                d_risk >= self.config.agreement_threshold
                and i_risk >= self.config.agreement_threshold
            )
            if both_fired:
                base = min(base * self.config.agreement_bonus, 1.0)
        elif d_available:
            base = d_risk
        elif i_available:
            base = i_risk
        else:
            base = 0.0

        # Stage 4: provenance adjustment
        prov_result = provenance.adjust(base, effective_source, self._provenance_config)
        final_risk = prov_result.risk

        # Stage 5: classification
        severity = classify(final_risk)

        # Build human-readable match labels
        matches: list[str] = []
        if d_risk >= 0.3:
            matches.append(f"density={d_risk:.2f}")
        if i_risk >= 0.3:
            matches.append(f"discontinuity={i_risk:.2f}")
        if prov_result.multiplier != 1.0:
            matches.append(
                f"provenance={effective_source}({prov_result.multiplier:.1f}x)"
            )

        # Merge hotspots from both signals, sorted by start offset
        hotspots = sorted(
            set(density_result.hotspots) | set(disc_result.hotspots),
            key=lambda h: h[0],
        )

        return ScanResult(
            severity=severity,
            risk=final_risk,
            source=effective_source,
            density_risk=d_risk,
            discontinuity_risk=i_risk,
            provenance_multiplier=prov_result.multiplier,
            matches=matches,
            hotspots=hotspots,
        )

    def protect(
        self,
        arg_name: str | None = None,
        source: str | None = None,
    ) -> Callable[[Callable[..., _T]], Callable[..., _T]]:
        """Decorator that scans an argument before calling the function.

        If the scan result is at or above the configured block severity,
        InjectionRiskError is raised with the ScanResult attached.

        Args:
            arg_name: Name of the keyword argument to scan. If None, the
                first positional argument is scanned.
            source: Optional provenance source override for the scan.

        Returns:
            A decorator that wraps the target function.
        """

        def decorator(func: Callable[..., _T]) -> Callable[..., _T]:
            @functools.wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> _T:
                text = (
                    kwargs.get(arg_name, "")
                    if arg_name is not None
                    else args[0] if args else ""
                )

                result = self.scan(str(text), source=source)
                if result.is_blocking(self.config.block_severity):
                    raise InjectionRiskError(result)

                return func(*args, **kwargs)

            return wrapper

        return decorator


__all__ = ["ContextScanner", "ScanResult", "ScannerConfig", "classify"]
