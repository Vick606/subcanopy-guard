# Scanner

The `scanner` module is the public API of Subcanopy Guard. It composes
the three detection signals into a single `ContextScanner` object,
applies an optional decoding pass, and returns a structured `ScanResult`.

This document explains the composition strategy, the design decisions
behind each threshold, and the optional decoding behavior. For the
detection techniques themselves, see the other docs in this directory.

## Composition strategy

The scanner runs three signals and combines them in a specific order.

### Stage 1: Density and discontinuity

Density and discontinuity are the primary signals. They are combined
with a weighted sum:

    base = 0.6 * density + 0.4 * discontinuity

Density gets the higher weight because it operates on the local window
and is structurally immune to context dilution. Discontinuity is the
companion signal that catches style breaks, but it requires at least
three sentences to compute, so it is unavailable on short inputs.

### The availability rule

If a signal cannot be computed, it does not vote against a signal that
can. This is the single most important design decision in the module.

The original implementation multiplied both signals unconditionally:

    base = 0.6 * density + 0.4 * discontinuity

When discontinuity was unavailable (input was a single sentence), it
returned 0.0 and acted as a phantom "not malicious" vote. A single
sentence injection like "Ignore all previous instructions" scored 0.75
on density, but the final risk was only 0.45 because 0.4 * 0 was
subtracted as if discontinuity had voted.

The fix was found during PromptWall generalization testing. The new
behavior:

    if both signals are available:
        base = 0.6 * density + 0.4 * discontinuity
        if both exceed 0.3:
            base *= 1.15    # agreement bonus
    elif only density is available:
        base = density
    elif only discontinuity is available:
        base = discontinuity
    else:
        base = 0.0

Impact: PromptWall direct_injection recall went from 9.5% to 22.1%.

### The agreement bonus

When both signals fire above 0.3, the combined risk is multiplied by
1.15 (capped at 1.0). Independent agreement between two different
detection mechanisms is a stronger signal than either alone.

A strong single signal is not penalized by a weak companion. Density
0.75 combined with discontinuity 0.10 stays at 0.49, unchanged. But
density 0.75 combined with discontinuity 0.35 becomes
`(0.6*0.75 + 0.4*0.35) * 1.15 = 0.68`.

### Stage 2: Provenance adjustment

After the density and discontinuity signals are combined, a source-aware
multiplier is applied. See docs/provenance.md for the multiplier values
and rationale.

    final = min(base * provenance_multiplier, 1.0)

### Stage 3: Severity classification

The final risk score is mapped to a severity label:

| Risk range | Severity |
|---|---|
| >= 0.75 | CRITICAL |
| 0.55 to 0.75 | HIGH |
| 0.35 to 0.55 | MEDIUM |
| 0.15 to 0.35 | LOW |
| < 0.15 | CLEAN |

The bands follow the ASCEND severity model and the threat levels used
by the tester311249/llm-security project. The specific boundary values
were chosen so that a single STRONG verb or a single jailbreak phrase
pushes a window to HIGH on its own.

## Optional decoding pass

The `decode_encoded` flag in `ScannerConfig` enables a second scan pass
on normalized text. Default is False.

### What happens when enabled

1. The input is normalized: homoglyph folding, then base64 and Morse
   segment detection and replacement.
2. If the normalized text is identical to the input, no second pass runs.
3. Otherwise, the decoded text is scanned through the same three signals.
4. The result with the higher risk score wins.
5. If the decoded pass wins, `ScanResult.decoded` is set to True.

### Why opt-in

The decode pass adds latency and can produce false positives on text
that happens to contain base64-shaped strings. Deployments that only
handle plain text should not pay the cost. Deployments that handle
tool output from arbitrary sources should enable it.

Default off also means the upgrade from v0.3.1 to v0.4.0 is behavior
preserving. Users see no difference until they enable the flag.

### The `decoded` field

`ScanResult.decoded` tells you which pass produced the result. Useful
for logging and for detecting whether an attacker attempted encoding
evasion. A scan with `decoded=True` means the scanner had to normalize
or decode the input before it could detect the payload.

## Thresholds that require benchmark measurement

The following values were tuned against the AgentDojo v1 and PromptWall
benchmarks. Changing any of them requires re-running both benchmarks and
documenting the impact in the commit message.

| Setting | Value | Location |
|---|---|---|
| Density weight | 0.6 | `_DENSITY_WEIGHT` |
| Discontinuity weight | 0.4 | `_DISCONTINUITY_WEIGHT` |
| Agreement threshold | 0.3 | `_AGREEMENT_THRESHOLD` |
| Agreement bonus | 1.15 | `_AGREEMENT_BONUS` |
| Severity bands | see table above | `_SEVERITY_BANDS` |

To measure:

    uv run python -m bench.run --block-at CRITICAL
    uv run python -m bench.promptwall --per-category

## References

- ASCEND severity model: critical / high / medium / low / info
- tester311249/llm-security: SAFE / LOW / MEDIUM / HIGH / CRITICAL
- LLM Guard: scanner composition pattern
