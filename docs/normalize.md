# Normalization

The `normalize` module handles character-level and encoding-level evasion
techniques used to bypass prompt injection detectors. This document
explains what each technique is, why it works, how the module defends
against it, and where the defense still fails.

## Why this module exists

Regex-based and lexicon-based detectors match on specific strings. An
attacker can defeat them by changing the bytes without changing the
visual appearance of the text. Two classes of evasion are relevant:

**Character substitution.** Replace Latin characters with visually
identical Cyrillic or Greek characters. "ignore" becomes "іgnore" with
a Cyrillic і (U+0456). The regex never matches. NFKC normalization does
not fix this on its own, because Cyrillic characters are not compatibility
variants of Latin characters.

**Encoding.** Wrap the payload in base64. "ignore all previous
instructions" becomes "aWdub3JlIGFsbCBwcmV2aW91cyBpbnN0cnVjdGlvbnM=".
The string has no injection-related words, so a lexicon-based detector
scores it as CLEAN.

Both are trivial for an attacker to apply and both are documented in
real-world prompt injection incidents.

## Homoglyph folding

### The technique

The `fold_homoglyphs` function applies a three-stage pipeline:

**Stage 1: NFKC normalization.** The Unicode standard defines NFKC as
"compatibility decomposition followed by canonical composition." It
collapses fullwidth Latin characters, mathematical script variants,
ligatures, and other compatibility forms to their canonical equivalents.
For example, "ｉｇｎｏｒｅ" (fullwidth) becomes "ignore".

NFKC does not convert Cyrillic to Latin. It only handles characters that
are explicitly marked as compatibility variants of each other.

**Stage 2: Invisible character stripping.** Zero-width spaces, bidi
overrides, and soft hyphens are removed. These characters render as
nothing but occupy a position in the string. An attacker can insert them
between letters to break regex matching without changing the visual
appearance. "ig\u200bnore" looks identical to "ignore" on screen.

**Stage 3: Explicit homoglyph mapping.** A curated dictionary maps
Cyrillic, Greek, and Turkish dotless-i characters to their ASCII
equivalents. This is the step that NFKC cannot do.

### Sources

The homoglyph mapping is derived from:

- Unicode UTS #39: Unicode Security Mechanisms, which defines the
  confusables.txt dataset
- OWASP LLM Prompt Injection Prevention Cheat Sheet
- The `prompt-injection-sanitizer` project's homoglyph tables
- The `navi-sanitize` project's confusable mapping

The mapping is curated for prompt injection detection. It covers the
characters most likely to appear in injection keywords: ignore,
disregard, instructions, system, prompt, override, forget, reveal,
execute, disable, restrictions.

### Limitations

- **Not exhaustive.** Unicode has thousands of confusable characters.
  The mapping covers the most common ones. A determined attacker using
  an obscure lookalike may still evade detection.
- **Legitimate Cyrillic and Greek text is affected.** Russian text
  containing the Cyrillic character "о" will have that character
  converted to Latin "o". This is a deliberate tradeoff: the scanner
  is designed for English-language prompt injection detection, and
  the false-positive cost of the mapping is low because the density
  signal operates on English keywords.

## Base64 detection

### The technique

Base64 encoding converts arbitrary bytes into a 64-character alphabet
(A-Z, a-z, 0-9, +, /) with padding. It is used throughout computing for
encoding binary data in text-safe form: email attachments, JSON Web
Tokens, image data URIs.

For an attacker, base64 is a free obfuscation layer. Any injection
payload can be encoded in one line of code. The encoded string contains
none of the original keywords.

### Detection approach

A naive detection pattern like `[A-Za-z0-9+/]{20,}` matches enormous
amounts of legitimate text: session IDs, git hashes, filenames, UUIDs,
JWT fragments. Published analysis of production systems found that a
regex-only base64 detector has a false-positive rate above 1000% — it
flags more legitimate strings than actual payloads.

The `find_base64_segments` function applies four filters in sequence.
A candidate must pass all of them:

**Filter 1: Minimum length.** At least 20 characters. Short strings
are ambiguous and produce noise.

**Filter 2: Entropy.** Shannon entropy must be at least 4.0 bits per
character. Base64 of English text scores 4.5 to 5.0. Base64 of binary
data scores 5.5 to 6.0. Legitimate structured strings like repeated
identifiers score below 3.5. The threshold of 4.0 accepts real payloads
and rejects most lookalikes.

**Filter 3: Round-trip validation.** Decode the candidate, then
re-encode it, and compare the result to the original. Invalid base64
produces a different string on re-encoding. This eliminates candidates
that matched the regex but are not actually valid base64.

**Filter 4: Printable output.** The decoded bytes must be at least 85
percent printable ASCII. Base64 of images, compressed files, and other
binary data decodes to non-printable output and is rejected. This
matters because the goal is detecting text-based payloads, not binaries.

### Why entropy filtering

Shannon entropy measures the average information content per character.
A string with high entropy has characters distributed roughly uniformly.
A string with low entropy has a skewed distribution.

- "aaaaaaaaaaaaaaaaaaaa" — entropy 0.0 (one distinct character)
- "abcabcabcabcabcabcab" — entropy ~1.6 (three characters, uniform)
- "aWdub3JlIGFsbCBwcmV2aW91cyBpbnN0cnVjdGlvbnM" — entropy 4.74
  (base64 of "ignore all previous instructions")

The threshold of 4.0 distinguishes real base64 (computed on varied
input) from structured identifiers. It is deliberately on the
permissive side, because false positives at the detection stage
are eliminated downstream: a flagged segment only matters if the
*decoded* content also triggers the density signal.

### Limitations

- **Payloads under 20 characters are not caught.** A short base64
  string like "aWdub3Jl" (decode: "ignore") is below the length
  threshold. This is a deliberate tradeoff to control false positives.
- **Double-encoded payloads are not caught.** Base64 of base64 of
  an injection is not decoded twice. The roadmap does not currently
  plan to add this.
- **Custom alphabets are not caught.** Rot13, hex, or a shuffled
  base64 alphabet will not decode correctly and will be rejected
  by round-trip validation.

## Integration with the scanner

The `fold_homoglyphs` function is intended to run as a preprocessing
step. Call it on the input before passing to `ContextScanner.scan()`.
The scanner's own two-pass logic (added in v0.4.0) uses
`find_encoded_segments` and `apply_segments` to run a second pass on
the decoded view when `decode_encoded=True`.

## References

**Unicode UTS #39: Unicode Security Mechanisms.**
Unicode Consortium. Confusables and Mixed-Script Detection.
https://unicode.org/reports/tr39/

**OWASP LLM Prompt Injection Prevention Cheat Sheet.**
OWASP Foundation.
https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html

**OWASP AISVS C02-01: Prompt Injection Defense.**
OWASP AI Security and Privacy Guide.

**prompt-injection-sanitizer.**
Socket.dev analysis of homoglyph and zero-width evasion in production
prompt injection defenses. 2026.

**navi-sanitize.**
Project-Navi. Confusable character mapping and Unicode normalization
for LLM input sanitization. 2026.

**Base64 detection false positive rates.**
Multiple sources report that regex-only base64 detection produces
false-positive rates above 1000 percent on production text. Entropy
filtering is the standard mitigation.

## Morse code detection

### The technique

Morse code encodes text as sequences of dots and dashes, with spaces
between letters and slashes between words. It is a documented prompt
injection vector. In May 2026, an attacker used a Morse-encoded message
to trick an AI agent into transferring approximately $150,000 in crypto
tokens. The message bypassed every text-based filter because the encoded
string contains none of the original keywords.

NVIDIA's Garak vulnerability scanner includes `encoding.InjectMorse` as
a standard probe for testing whether models can be tricked into decoding
and executing Morse-encoded payloads.

### Detection approach

The `find_morse_segments` function applies three filters:

**Filter 1: Candidate matching.** A regex finds sequences of dots,
dashes, spaces, and slashes that are at least 10 characters long. The
regex accepts Unicode variants of dots (middle dot, bullet) and dashes
(en dash, em dash, minus sign) that attackers may use to evade
ASCII-only patterns.

**Filter 2: Decoding.** The candidate is normalized to standard dots and
dashes, then split into words and letters. Each letter is looked up in
the ITU Morse alphabet. If any code is not in the alphabet, the
candidate is rejected.

**Filter 3: Output validation.** The decoded text must be printable
ASCII and must contain at least three alphabetic characters. This
rejects Morse-like punctuation sequences that decode to noise.

### Limitations

- **Only ITU standard Morse is decoded.** Non-standard variants
  (American Morse, or custom mappings) are not supported.
- **Very short Morse messages are not caught.** A single letter like
  ".-" is below the 10-character threshold.
- **Morse embedded in other text may be missed.** The candidate regex
  requires a contiguous run of Morse characters.

### References for Morse detection

- Grok Morse code prompt injection incident, May 2026
- NVIDIA Garak `encoding.InjectMorse` probe
- ITU-R M.1677: International Morse Code
