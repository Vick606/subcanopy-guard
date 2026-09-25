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

"""Provenance-aware risk adjustment.

Not all text is equally trusted. A system prompt written by the developer
should never trip the scanner on its own. A tool output returned by an
external service should be held to a lower bar.

This module applies a multiplicative adjustment to a base risk score
based on where the text came from. The multipliers are intentionally
simple and auditable: an operator can explain to an auditor exactly
why a tool output was flagged and a system prompt was not.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Default multipliers
# ---------------------------------------------------------------------------
# These are RISK multipliers, not threshold multipliers. Higher value
# means "this source deserves more suspicion."
#
#   risk < 1.0  ->  dampen the base risk (trusted source)
#   risk = 1.0  ->  baseline (no adjustment)
#   risk > 1.0  ->  amplify the base risk (untrusted source)

_DEFAULT_MULTIPLIERS: dict[str, float] = {
    "system_prompt": 0.5,
    "user_input": 1.0,
    "retrieved_doc": 1.3,
    "tool_output": 1.5,
}

_DEFAULT_MULTIPLIER = 1.0


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class ProvenanceConfig:
    """Configuration for provenance-aware risk adjustment."""

    multipliers: dict[str, float] = field(
        default_factory=lambda: dict(_DEFAULT_MULTIPLIERS)
    )
    """Mapping of source tag to risk multiplier."""

    default_multiplier: float = _DEFAULT_MULTIPLIER
    """Multiplier used for sources not present in ``multipliers``."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@dataclass
class ProvenanceResult:
    """Result of applying provenance adjustment."""

    risk: float
    """Adjusted risk score in [0.0, 1.0]."""

    multiplier: float
    """The multiplier that was applied."""

    source: str
    """The source tag that was passed in."""


def adjust(
    risk: float,
    source: str,
    config: ProvenanceConfig | None = None,
) -> ProvenanceResult:
    """Adjust a base risk score according to the source of the text.

    Args:
        risk: Base risk score in [0.0, 1.0], typically from density and/or
            discontinuity. Values outside this range are clamped.
        source: Source tag, e.g. ``"tool_output"``, ``"user_input"``,
            ``"system_prompt"``, ``"retrieved_doc"``. Unknown sources use
            the configured default multiplier.
        config: Optional configuration override.

    Returns:
        A ProvenanceResult with the adjusted risk, the multiplier used,
        and the source.
    """
    cfg = config or ProvenanceConfig()

    # Clamp input to [0.0, 1.0] so callers can't accidentally feed
    # already-out-of-range values that would misbehave after adjustment.
    base = max(0.0, min(risk, 1.0))

    multiplier = cfg.multipliers.get(source, cfg.default_multiplier)
    adjusted = max(0.0, min(base * multiplier, 1.0))

    return ProvenanceResult(
        risk=adjusted,
        multiplier=multiplier,
        source=source,
    )


def known_sources(config: ProvenanceConfig | None = None) -> list[str]:
    """Return the list of source tags with explicit multipliers."""
    cfg = config or ProvenanceConfig()
    return sorted(cfg.multipliers.keys())
