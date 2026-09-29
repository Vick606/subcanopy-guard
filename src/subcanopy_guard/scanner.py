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

"""Public scanner API. See docs/scanner.md for design notes."""

from __future__ import annotations

import functools
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

from subcanopy_guard import density, discontinuity, normalize, provenance
from subcanopy_guard.exceptions import InjectionRiskError

_DENSITY_WEIGHT = 0.6
_DISCONTINUITY_WEIGHT = 0.4
_AGREEMENT_THRESHOLD = 0.3
_AGREEMENT_BONUS = 1.15

_SEVERITY_BANDS: tuple[tuple[float, str], ...] = (
    (0.75, "CRITICAL"),
    (0.55, "HIGH"),
    (0.35, "MEDIUM"),
    (0.15, "LOW"),
    (0.0, "CLEAN"),
)

_T = TypeVar("_T")


@dataclass
class ScannerConfig:
    """Configuration for the ContextScanner."""

    density_weight: float = _DENSITY_WEIGHT
    discontinuity_weight: float = _DISCONTINUITY_WEIGHT
    agreement_threshold: float = _AGREEMENT_THRESHOLD
    agreement_bonus: float = _AGREEMENT_BONUS
    block_severity: str = "HIGH"
    decode_encoded: bool = False


@dataclass
class ScanResult:
    """Structured result of a scan."""

    severity: str
    risk: float
    source: str
    density_risk: float = 0.0
    discontinuity_risk: float = 0.0
    provenance_multiplier: float = 1.0
    matches: list[str] = field(default_factory=list)
    hotspots: list[tuple[int, int]] = field(default_factory=list)
    decoded: bool = False

    def is_blocking(self, threshold: str = "HIGH") -> bool:
        """Return True if severity is at or above the given threshold."""
        order = {"CLEAN": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
        return order.get(self.severity, 0) >= order.get(threshold, 3)


def classify(risk: float) -> str:
    """Map a normalized risk score to a severity label."""
    for boundary, label in _SEVERITY_BANDS:
        if risk >= boundary:
            return label
    return "CLEAN"


class ContextScanner:
    """Context-aware indirect prompt injection scanner.

    Composes density, discontinuity, and provenance signals. Stateless
    and reentrant.
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
            source: Optional provenance source override.

        Returns:
            A ScanResult with severity, risk, contributions, and hotspots.
        """
        effective_source = source or self.source
        result = self._run_signals(text, effective_source)

        if self.config.decode_encoded:
            result = self._scan_with_decoding(text, effective_source, result)

        return result

    def _scan_with_decoding(
        self,
        text: str,
        source: str,
        baseline: ScanResult,
    ) -> ScanResult:
        """Run a second pass on the normalized and decoded text."""
        normalized = normalize.fold_homoglyphs(text)

        segments = normalize.find_encoded_segments(normalized)
        if segments:
            normalized = normalize.apply_segments(normalized, segments)

        if normalized == text:
            return baseline

        decoded_result = self._run_signals(normalized, source)

        if decoded_result.risk > baseline.risk:
            decoded_result.decoded = True
            return decoded_result

        return baseline

    def _run_signals(self, text: str, source: str) -> ScanResult:
        """Run the three signals on text and produce a ScanResult."""
        density_result = density.score(text, self._density_config)
        d_risk = density_result.risk

        disc_result = discontinuity.score(text, self._discontinuity_config)
        i_risk = disc_result.risk

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

        prov_result = provenance.adjust(base, source, self._provenance_config)
        final_risk = prov_result.risk
        severity = classify(final_risk)

        matches: list[str] = []
        if d_risk >= 0.3:
            matches.append(f"density={d_risk:.2f}")
        if i_risk >= 0.3:
            matches.append(f"discontinuity={i_risk:.2f}")
        if prov_result.multiplier != 1.0:
            matches.append(f"provenance={source}({prov_result.multiplier:.1f}x)")

        hotspots = sorted(
            set(density_result.hotspots) | set(disc_result.hotspots),
            key=lambda h: h[0],
        )

        return ScanResult(
            severity=severity,
            risk=final_risk,
            source=source,
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

        Args:
            arg_name: Keyword argument name. If None, the first positional
                argument is scanned.
            source: Optional provenance source override.

        Returns:
            A decorator that raises InjectionRiskError on blocking severity.
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
