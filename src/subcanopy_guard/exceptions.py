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

"""Exceptions raised by Subcanopy Guard."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from subcanopy_guard.scanner import ScanResult


class SubcanopyError(Exception):
    """Base exception for all Subcanopy Guard errors."""


class InjectionRiskError(SubcanopyError):
    """Raised when a scan detects an injection at HIGH or CRITICAL severity."""

    def __init__(self, result: ScanResult) -> None:
        self.result = result
        super().__init__(
            f"Injection risk detected: severity={result.severity}, "
            f"score={result.risk:.2f}, matches={result.matches}"
        )
