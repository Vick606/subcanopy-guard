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

Stage 0 provides a placeholder that satisfies the public surface area
(ContextScanner and ScanResult) so downstream tooling imports cleanly.
The detection logic is implemented in Stage 4.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ScanResult:
    """Structured result of a scan."""

    severity: str = "CLEAN"
    risk: float = 0.0
    matches: list[str] = field(default_factory=list)
    hotspots: list[tuple[int, int]] = field(default_factory=list)


class ContextScanner:
    """Context-aware indirect prompt injection scanner.

    Placeholder implementation for Stage 0.
    """

    def __init__(self, source: str = "user_input") -> None:
        self.source = source

    def scan(self, text: str) -> ScanResult:
        """Scan text and return a ScanResult."""
        raise NotImplementedError("ContextScanner.scan is implemented in Stage 4")
