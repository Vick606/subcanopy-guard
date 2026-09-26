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

"""Subcanopy Guard - context-aware indirect prompt injection scanner."""

from importlib.metadata import PackageNotFoundError, version

from subcanopy_guard.exceptions import InjectionRiskError
from subcanopy_guard.scanner import ContextScanner, ScanResult

try:
    __version__ = version("subcanopy-guard")
except PackageNotFoundError:
    # Package is not installed (e.g. running from a source checkout
    # without `uv sync`). Fall back to a clear marker rather than
    # silently reporting a stale number.
    __version__ = "0.0.0+unknown"

__all__ = ["ContextScanner", "ScanResult", "InjectionRiskError", "__version__"]
