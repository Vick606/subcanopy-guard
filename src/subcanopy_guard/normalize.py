# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Victor

"""Text normalization for encoded and obfuscated payloads.

Defeats character-level evasion (homoglyphs, zero-width characters) and
encoding evasion (base64, Morse) before scanning. See docs/normalize.md
for the rationale, sources, and known limitations of each technique.
"""

from __future__ import annotations

import base64
import math
import re
import unicodedata
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Homoglyph folding
# ---------------------------------------------------------------------------

_INVISIBLE_CHARS: frozenset[str] = frozenset(
    {
        "\u200b", "\u200c", "\u200d", "\u200e", "\u200f",
        "\u202a", "\u202b", "\u202c", "\u202d", "\u202e",
        "\u2060", "\u2061", "\u2062", "\u2063", "\u2064",
        "\ufeff", "\u00ad",
    }
)

_HOMOGLYPH_MAP: dict[str, str] = {
    # Cyrillic lookalikes (lowercase)
    "\u0430": "a", "\u0432": "b", "\u0435": "e", "\u043a": "k",
    "\u043c": "m", "\u043d": "h", "\u043e": "o", "\u0440": "p",
    "\u0441": "c", "\u0442": "t", "\u0443": "y", "\u0445": "x",
    "\u0455": "s", "\u0456": "i", "\u0458": "j", "\u04bb": "h",
    "\u04cf": "l", "\u0501": "d", "\u051b": "q", "\u051d": "w",
    # Cyrillic lookalikes (uppercase)
    "\u0410": "A", "\u0412": "B", "\u0415": "E", "\u041a": "K",
    "\u041c": "M", "\u041d": "H", "\u041e": "O", "\u0420": "P",
    "\u0421": "C", "\u0422": "T", "\u0423": "Y", "\u0425": "X",
    "\u0405": "S", "\u0406": "I", "\u0408": "J",
    # Greek lookalikes
    "\u03b1": "a", "\u03b5": "e", "\u03b9": "i", "\u03ba": "k",
    "\u03bd": "v", "\u03bf": "o", "\u03c1": "p", "\u03c4": "t",
    "\u03c5": "u", "\u03c7": "x",
    "\u0391": "A", "\u0392": "B", "\u0395": "E", "\u0396": "Z",
    "\u0397": "H", "\u0399": "I", "\u039a": "K", "\u039c": "M",
    "\u039d": "N", "\u039f": "O", "\u03a1": "P", "\u03a4": "T",
    "\u03a5": "Y", "\u03a7": "X",
    # Turkish dotless-i
    "\u0131": "i", "\u0130": "I",
    # Other lookalikes
    "\u01c0": "l", "\u01c3": "!", "\u2223": "|", "\uff5c": "|",
}


def fold_homoglyphs(text: str) -> str:
    """Normalize text to defeat homoglyph and zero-width evasion.

    Applies NFKC normalization, strips invisible characters, then maps
    Cyrillic and Greek lookalikes plus Turkish dotless-i to ASCII.
    """
    normalized = unicodedata.normalize("NFKC", text)
    stripped = "".join(ch for ch in normalized if ch not in _INVISIBLE_CHARS)
    return "".join(_HOMOGLYPH_MAP.get(ch, ch) for ch in stripped)


def count_invisible(text: str) -> int:
    """Return the number of invisible characters in text."""
    return sum(1 for ch in text if ch in _INVISIBLE_CHARS)


def count_homoglyphs(text: str) -> int:
    """Return the number of mapped homoglyph characters in text."""
    return sum(1 for ch in text if ch in _HOMOGLYPH_MAP)


# ---------------------------------------------------------------------------
# Shared types and helpers
# ---------------------------------------------------------------------------


@dataclass
class EncodedSegment:
    """A decoded segment found in a larger text."""

    start: int
    end: int
    encoding: str
    original: str
    decoded: str
    entropy: float


def _shannon_entropy(s: str) -> float:
    """Compute Shannon entropy of a string in bits per character."""
    if not s:
        return 0.0
    counts: dict[str, int] = {}
    for ch in s:
        counts[ch] = counts.get(ch, 0) + 1
    n = len(s)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def _is_printable(text: str, min_ratio: float = 0.85) -> bool:
    """Check that at least min_ratio of text is printable ASCII."""
    if not text:
        return False
    printable = sum(1 for ch in text if ch.isprintable() or ch in "\n\r\t")
    return (printable / len(text)) >= min_ratio


# ---------------------------------------------------------------------------
# Base64 detection
# ---------------------------------------------------------------------------

# Single pattern matching both alphabets. The character class includes
# standard (+/) and URL-safe (-_) special characters.
_BASE64_RE = re.compile(r"[A-Za-z0-9+/\-_]{20,}={0,2}")

_MIN_BASE64_LENGTH = 20
_MIN_BASE64_ENTROPY = 4.0


def _classify_base64_encoding(candidate: str) -> str:
    """Classify a base64 candidate as standard or URL-safe.

    Standard base64 uses + and /. URL-safe uses - and _.
    If the string contains neither, it is valid in both alphabets;
    default to standard base64 (the more common format).
    """
    if "-" in candidate or "_" in candidate:
        return "base64url"
    return "base64"


def _try_base64_decode(candidate: str) -> str | None:
    """Decode a candidate, validating via round-trip and printable check."""
    for altchars in (None, b"-_"):
        try:
            padded = candidate + "=" * (-len(candidate) % 4)
            decoded_bytes = base64.b64decode(padded, altchars=altchars)
        except (ValueError, TypeError):
            continue

        try:
            re_encoded = base64.b64encode(decoded_bytes).decode("ascii").rstrip("=")
            if altchars == b"-_":
                re_encoded = re_encoded.replace("+", "-").replace("/", "_")
            if re_encoded != candidate.rstrip("="):
                continue
        except (ValueError, TypeError):
            continue

        try:
            decoded_text = decoded_bytes.decode("utf-8")
        except UnicodeDecodeError:
            continue

        if not _is_printable(decoded_text):
            continue

        return decoded_text

    return None


def find_base64_segments(text: str) -> list[EncodedSegment]:
    """Find base64-encoded segments in text.

    Uses a single regex matching both alphabets, then classifies each
    candidate by inspecting its special characters. Filters by length,
    entropy, round-trip decode, and printable output.
    """
    if not text:
        return []

    segments: list[EncodedSegment] = []

    for match in _BASE64_RE.finditer(text):
        candidate = match.group(0)
        if len(candidate) < _MIN_BASE64_LENGTH:
            continue

        entropy = _shannon_entropy(candidate)
        if entropy < _MIN_BASE64_ENTROPY:
            continue

        decoded = _try_base64_decode(candidate)
        if decoded is None:
            continue

        segments.append(
            EncodedSegment(
                start=match.start(),
                end=match.end(),
                encoding=_classify_base64_encoding(candidate),
                original=candidate,
                decoded=decoded,
                entropy=entropy,
            )
        )

    segments.sort(key=lambda s: s.start)
    return segments


# ---------------------------------------------------------------------------
# Morse code detection
# ---------------------------------------------------------------------------
# Morse code is a documented prompt injection vector. The Grok incident
# in May 2026 used Morse to bypass safety filters. NVIDIA's Garak scanner
# includes encoding.InjectMorse as a standard probe. Detection follows
# the same pattern as base64: find candidates, decode, validate.

_MORSE_ALPHABET: dict[str, str] = {
    ".-": "A", "-...": "B", "-.-.": "C", "-..": "D", ".": "E",
    "..-.": "F", "--.": "G", "....": "H", "..": "I", ".---": "J",
    "-.-": "K", ".-..": "L", "--": "M", "-.": "N", "---": "O",
    ".--.": "P", "--.-": "Q", ".-.": "R", "...": "S", "-": "T",
    "..-": "U", "...-": "V", ".--": "W", "-..-": "X", "-.--": "Y",
    "--..": "Z",
    "-----": "0", ".----": "1", "..---": "2", "...--": "3",
    "....-": "4", ".....": "5", "-....": "6", "--...": "7",
    "---..": "8", "----.": "9",
    ".-.-.-": ".", "--..--": ",", "..--..": "?", "-....-": "-",
    "-..-.": "/", "-.--.": "(", "-.--.-": ")", ".-..-.": '"',
    "---...": ":", "-.-.--": "!", ".----.": "'", "-...-": "=",
    ".-.-.": "+", "-.-.-.": ";", "..--.-": "_", ".-...": "&",
    "...-..-": "$", ".--.-.": "@",
}

# Characters normalized to dot and dash before matching.
_MORSE_DOT_VARIANTS = frozenset({".", "\u00b7", "\u2022", "*"})
_MORSE_DASH_VARIANTS = frozenset({"-", "\u2013", "\u2014", "\u2212", "_"})

_MORSE_CANDIDATE_RE = re.compile(
    r"[.\-\u00b7\u2022*\u2013\u2014\u2212_/| ]{10,}"
)

_MIN_MORSE_LENGTH = 10
_MIN_MORSE_LETTERS = 3


def _normalize_morse(text: str) -> str:
    """Normalize Morse variants to standard dots, dashes, and separators."""
    result: list[str] = []
    for ch in text:
        if ch in _MORSE_DOT_VARIANTS:
            result.append(".")
        elif ch in _MORSE_DASH_VARIANTS:
            result.append("-")
        elif ch in "/|":
            result.append("/")
        else:
            result.append(ch)
    return "".join(result)


def _decode_morse(candidate: str) -> str | None:
    """Decode a Morse candidate. Returns None on failure."""
    normalized = _normalize_morse(candidate).strip()
    if not normalized:
        return None

    words = normalized.split("/")
    decoded_words: list[str] = []

    for word in words:
        letters = word.strip().split()
        if not letters:
            continue
        decoded_letters: list[str] = []
        for code in letters:
            if code not in _MORSE_ALPHABET:
                return None
            decoded_letters.append(_MORSE_ALPHABET[code])
        decoded_words.append("".join(decoded_letters))

    if not decoded_words:
        return None

    decoded = " ".join(decoded_words)
    if not decoded or not _is_printable(decoded):
        return None

    # Require enough decoded letters to avoid matching punctuation noise.
    if sum(1 for c in decoded if c.isalpha()) < _MIN_MORSE_LETTERS:
        return None

    return decoded


def find_morse_segments(text: str) -> list[EncodedSegment]:
    """Find Morse code segments in text.

    Detects sequences of dots and dashes with spaces and slashes as
    separators. Decodes via the ITU standard alphabet and validates
    that the output is printable text with enough alphabetic content.
    """
    if not text:
        return []

    segments: list[EncodedSegment] = []

    for match in _MORSE_CANDIDATE_RE.finditer(text):
        candidate = match.group(0)
        if len(candidate) < _MIN_MORSE_LENGTH:
            continue

        decoded = _decode_morse(candidate)
        if decoded is None:
            continue

        segments.append(
            EncodedSegment(
                start=match.start(),
                end=match.end(),
                encoding="morse",
                original=candidate,
                decoded=decoded,
                entropy=_shannon_entropy(candidate),
            )
        )

    segments.sort(key=lambda s: s.start)
    return segments


# ---------------------------------------------------------------------------
# Public composition
# ---------------------------------------------------------------------------


def apply_segments(text: str, segments: list[EncodedSegment]) -> str:
    """Replace encoded segments with their decoded text."""
    if not segments:
        return text

    parts: list[str] = []
    last_end = 0
    for seg in segments:
        parts.append(text[last_end : seg.start])
        parts.append(seg.decoded)
        last_end = seg.end
    parts.append(text[last_end:])
    return "".join(parts)


def find_encoded_segments(text: str) -> list[EncodedSegment]:
    """Find all encoded segments. Supports base64 and Morse."""
    segments = find_base64_segments(text) + find_morse_segments(text)
    segments.sort(key=lambda s: s.start)
    return segments
