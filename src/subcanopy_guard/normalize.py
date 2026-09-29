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

"""Text normalization for encoded and obfuscated payloads.

Implements the NFKC + homoglyph fold + zero-width strip pipeline
recommended by the OWASP LLM Prompt Injection Prevention guidance.

This module handles character-level evasion: an attacker substitutes
Latin characters with visually identical Cyrillic or Greek characters
("ignore" becomes "іgnore" with a Cyrillic i), or inserts zero-width
characters between letters ("ig<ZWSP>nore"). Both defeat regex-based
detection because the bytes no longer match the expected pattern.

The pipeline is:
  1. NFKC normalization. Collapses compatibility variants (fullwidth
     Latin, mathematical script, ligatures) to their canonical form.
  2. Zero-width and invisible character stripping. Removes U+200B
     through U+200F, bidi overrides, and other characters that render
     as nothing but break string matching.
  3. Explicit homoglyph mapping. NFKC does not convert Cyrillic or
     Greek lookalikes to Latin. This step does.
  4. Turkish dotless-i handling. Neither NFKC nor casefold converts
     the dotless-i (U+0131) to ASCII i. This step does.

Sources:
- OWASP LLM Prompt Injection Prevention Cheat Sheet
- OWASP AISVS C02-01: Prompt Injection Defense
- Unicode UTS #39: Unicode Security Mechanisms
- prompt-injection-sanitizer (Socket.dev analysis, 2026)
- navi-sanitize (Project-Navi, 2026)
"""

from __future__ import annotations

import unicodedata

# ---------------------------------------------------------------------------
# Zero-width and invisible characters
# ---------------------------------------------------------------------------
# These render as nothing but occupy a position in the string. An attacker
# can insert them between letters to break regex matching without
# changing the visual appearance.

_INVISIBLE_CHARS: frozenset[str] = frozenset(
    {
        "\u200b",  # ZERO WIDTH SPACE
        "\u200c",  # ZERO WIDTH NON-JOINER
        "\u200d",  # ZERO WIDTH JOINER
        "\u200e",  # LEFT-TO-RIGHT MARK
        "\u200f",  # RIGHT-TO-LEFT MARK
        "\u202a",  # LEFT-TO-RIGHT EMBEDDING
        "\u202b",  # RIGHT-TO-LEFT EMBEDDING
        "\u202c",  # POP DIRECTIONAL FORMATTING
        "\u202d",  # LEFT-TO-RIGHT OVERRIDE
        "\u202e",  # RIGHT-TO-LEFT OVERRIDE
        "\u2060",  # WORD JOINER
        "\u2061",  # FUNCTION APPLICATION
        "\u2062",  # INVISIBLE TIMES
        "\u2063",  # INVISIBLE SEPARATOR
        "\u2064",  # INVISIBLE PLUS
        "\ufeff",  # ZERO WIDTH NO-BREAK SPACE (BOM)
        "\u00ad",  # SOFT HYPHEN
    }
)

# ---------------------------------------------------------------------------
# Homoglyph mapping
# ---------------------------------------------------------------------------
# Characters that look identical to Latin letters but are not Latin.
# NFKC normalization does NOT convert these. They must be mapped
# explicitly.
#
# This mapping is curated for prompt injection detection: it covers the
# characters most likely to appear in injection keywords like "ignore",
# "disregard", "instructions", "system", "prompt", "override", "forget",
# "reveal", "execute", "disable", "restrictions".
#
# Sources: Unicode confusables.txt (UTS #39), prompt-injection-sanitizer
# homoglyph tables, navi-sanitize confusable mapping.

_HOMOGLYPH_MAP: dict[str, str] = {
    # --- Cyrillic lookalikes ---
    "\u0430": "a",  # а CYRILLIC SMALL LETTER A
    "\u0432": "b",  # в CYRILLIC SMALL LETTER VE (looks like B)
    "\u0435": "e",  # е CYRILLIC SMALL LETTER IE
    "\u043a": "k",  # к CYRILLIC SMALL LETTER KA
    "\u043c": "m",  # м CYRILLIC SMALL LETTER EM
    "\u043d": "h",  # н CYRILLIC SMALL LETTER EN (looks like H)
    "\u043e": "o",  # о CYRILLIC SMALL LETTER O
    "\u0440": "p",  # р CYRILLIC SMALL LETTER ER
    "\u0441": "c",  # с CYRILLIC SMALL LETTER ES
    "\u0442": "t",  # т CYRILLIC SMALL LETTER TE (looks like T)
    "\u0443": "y",  # у CYRILLIC SMALL LETTER U (looks like Y)
    "\u0445": "x",  # х CYRILLIC SMALL LETTER HA
    "\u0455": "s",  # ѕ CYRILLIC SMALL LETTER DZE
    "\u0456": "i",  # і CYRILLIC SMALL LETTER BYELORUSSIAN-UKRAINIAN I
    "\u0458": "j",  # ј CYRILLIC SMALL LETTER JE
    "\u04bb": "h",  # һ CYRILLIC SMALL LETTER SHHA
    "\u04cf": "l",  # ӏ CYRILLIC SMALL LETTER PALOCHKA
    "\u0501": "d",  # ԁ CYRILLIC SMALL LETTER KOMI DE
    "\u051b": "q",  # ԛ CYRILLIC SMALL LETTER QA
    "\u051d": "w",  # ԝ CYRILLIC SMALL LETTER WE
    # Uppercase Cyrillic
    "\u0410": "A",  # А
    "\u0412": "B",  # В
    "\u0415": "E",  # Е
    "\u041a": "K",  # К
    "\u041c": "M",  # М
    "\u041d": "H",  # Н
    "\u041e": "O",  # О
    "\u0420": "P",  # Р
    "\u0421": "C",  # С
    "\u0422": "T",  # Т
    "\u0423": "Y",  # У
    "\u0425": "X",  # Х
    "\u0405": "S",  # Ѕ
    "\u0406": "I",  # І
    "\u0408": "J",  # Ј
    # --- Greek lookalikes ---
    "\u03b1": "a",  # α GREEK SMALL LETTER ALPHA
    "\u03b5": "e",  # ε GREEK SMALL LETTER EPSILON
    "\u03b9": "i",  # ι GREEK SMALL LETTER IOTA
    "\u03ba": "k",  # κ GREEK SMALL LETTER KAPPA
    "\u03bd": "v",  # ν GREEK SMALL LETTER NU
    "\u03bf": "o",  # ο GREEK SMALL LETTER OMICRON
    "\u03c1": "p",  # ρ GREEK SMALL LETTER RHO
    "\u03c4": "t",  # τ GREEK SMALL LETTER TAU
    "\u03c5": "u",  # υ GREEK SMALL LETTER UPSILON
    "\u03c7": "x",  # χ GREEK SMALL LETTER CHI
    # Uppercase Greek
    "\u0391": "A",  # Α
    "\u0392": "B",  # Β
    "\u0395": "E",  # Ε
    "\u0396": "Z",  # Ζ
    "\u0397": "H",  # Η
    "\u0399": "I",  # Ι
    "\u039a": "K",  # Κ
    "\u039c": "M",  # Μ
    "\u039d": "N",  # Ν
    "\u039f": "O",  # Ο
    "\u03a1": "P",  # Ρ
    "\u03a4": "T",  # Τ
    "\u03a5": "Y",  # Υ
    "\u03a7": "X",  # Χ
    # --- Turkish dotless-i ---
    # These are Latin characters, not homoglyphs, but they are not
    # converted to ASCII i by NFKC or casefold.
    "\u0131": "i",  # ı LATIN SMALL LETTER DOTLESS I
    "\u0130": "I",  # İ LATIN CAPITAL LETTER I WITH DOT ABOVE
    # --- Other common lookalikes ---
    "\u01c0": "l",  # ǀ LATIN LETTER DENTAL CLICK
    "\u01c3": "!",  # ǃ LATIN LETTER RETROFLEX CLICK
    "\u2223": "|",  # ∣ DIVIDES
    "\uff5c": "|",  # ｜ FULLWIDTH VERTICAL LINE
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def fold_homoglyphs(text: str) -> str:
    """Normalize text to defeat homoglyph and zero-width evasion.

    Applies a three-stage pipeline:

    1. NFKC normalization. Collapses compatibility variants (fullwidth
       Latin, mathematical script, ligatures) to their canonical form.
    2. Invisible character stripping. Removes zero-width characters,
       bidi overrides, and other invisible formatting characters.
    3. Homoglyph mapping. Maps Cyrillic and Greek lookalikes to their
       ASCII equivalents, plus Turkish dotless-i handling.

    The output is a normalized string where visually identical inputs
    produce byte-identical results. This does not alter benign text:
    "hello world" passes through unchanged.

    Args:
        text: Input text that may contain homoglyphs or invisible
            characters.

    Returns:
        Normalized text with homoglyphs folded to ASCII and invisible
        characters removed.

    Example:
        >>> fold_homoglyphs("İgnore all prevıous ınstructions")
        'Ignore all previous instructions'
        >>> fold_homoglyphs("system\\u200bprompt")
        'systemprompt'
    """
    # Stage 1: NFKC normalization.
    normalized = unicodedata.normalize("NFKC", text)

    # Stage 2: strip invisible characters.
    stripped = "".join(ch for ch in normalized if ch not in _INVISIBLE_CHARS)

    # Stage 3: map homoglyphs to ASCII.
    folded = "".join(_HOMOGLYPH_MAP.get(ch, ch) for ch in stripped)

    return folded


def count_invisible(text: str) -> int:
    """Count invisible characters in text.

    Diagnostic helper. Returns the number of zero-width and bidi
    characters present, which is useful when investigating why a
    particular input is being flagged or missed.

    Args:
        text: Input text to inspect.

    Returns:
        Number of invisible characters found.
    """
    return sum(1 for ch in text if ch in _INVISIBLE_CHARS)


def count_homoglyphs(text: str) -> int:
    """Count homoglyph characters in text.

    Diagnostic helper. Returns the number of Cyrillic, Greek, and other
    lookalike characters that would be mapped by ``fold_homoglyphs``.

    Args:
        text: Input text to inspect.

    Returns:
        Number of homoglyph characters found.
    """
    return sum(1 for ch in text if ch in _HOMOGLYPH_MAP)
