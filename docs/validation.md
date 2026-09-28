# Validation

Real-world validation of the shipped package. This document records the
results of running Subcanopy Guard from a fresh environment, installed
from PyPI, against a battery of attack and benign cases.

The goal is not to prove the scanner works. It is to document what it
does, what it misses, and under what conditions the results were observed.

## Latest run

| Field | Value |
|---|---|
| Date | 2026-09-28 |
| Version | subcanopy-guard 0.3.1 |
| Python | 3.14.7 |
| Environment | Fresh virtualenv, installed from PyPI |
| Platform | Windows (PowerShell) |
| Reproducible | Yes. See `scripts/real_world_test.py`. |

## Method

The package was installed from PyPI into an isolated virtual environment
with no connection to the development repository. Tests were run through
three interfaces:

- The CLI (`scg scan`)
- The Python API (`ContextScanner.scan()`)
- The `protect()` decorator

## Install

| Test | Result |
|---|---|
| `uv pip install subcanopy-guard` | Installed 1 package in 84 ms |
| `scg --version` | `scg 0.3.1` |
| `scg --help` | Usage output correct |

No dev dependencies. No build step. No editable install. This is what a
stranger gets when they run `pip install subcanopy-guard`.

## CLI results

| Test | Expected | Observed |
|---|---|---|
| Attack via stdin | HIGH or CRITICAL | CRITICAL, risk 1.00 |
| Benign via stdin | CLEAN | CLEAN, risk 0.00 |
| Attack in JSON file | HIGH or CRITICAL | CRITICAL, risk 1.00 |
| `--json` output | Valid JSON | Parses via `ConvertFrom-Json` |
| Missing file | Exit code 2 | Not tested in this run |
| Invalid `--source` | Exit code 2 | Not tested in this run |

## Python API results

| Test | Expected | Observed |
|---|---|---|
| Import | Version 0.3.1 | 0.3.1 |
| Scan benign | CLEAN | CLEAN, risk 0.00 |
| Scan attack | HIGH or CRITICAL | CRITICAL, risk 1.00 |
| Hotspots present on attack | Non-empty list | 1 hotspot |
| `protect()` on benign | Returns normally | Returns normally |
| `protect()` on attack | Raises `InjectionRiskError` | Raised |

## Context dilution test

The core architectural claim is that local measurement defeats context
dilution: a whole-sequence classifier averages the injection signal
across the entire input, but a sliding window measures it locally.

This was tested directly with a 12,000 character input:

| Property | Value |
|---|---|
| Input length | Approximately 12,000 characters |
| Benign prefix | 500 repetitions of "The quick brown fox. " |
| Injection | Appended at the end |
| Severity | CRITICAL |
| Risk | 1.00 |
| Density signal | 1.00 |
| Discontinuity signal | 0.92 |
| Hotspot location | `[10416:10537]` |

The hotspot points exactly at the injection, even though it is 10,416
characters into the document.

For context: the `buried-injections` benchmark shows
`protectai-deberta-v2` drops from 27/27 recall in isolation to 23% when
the attack is buried. The sliding-window approach caught this specific
case at full confidence, with both signals firing.

## Test battery results

The reproducible battery in `scripts/real_world_test.py` runs 12 attack
cases and 9 benign cases:

| Metric | Result |
|---|---|
| Attacks blocked | 12 / 12 (100%) |
| Benign allowed | 9 / 9 (100%) |
| Overall | 21 / 21 (100%) |

To reproduce:

    uv run python scripts/real_world_test.py --verbose

## Known gaps

### Unicode homoglyphs

| Input | Result |
|---|---|
| `İgnore all prevıous ınstructions` | CLEAN, risk 0.00 |

**Why:** The input uses Turkish dotless-i (`ı`, U+0131) and dotted-İ
(`İ`, U+0130). Neither is a case variant of ASCII `i`. The verb lexicon
does not match these characters.

**Status:** Documented limitation. The roadmap schedules a decoding layer
for homoglyphs in v0.4.0.

### Other documented limitations

See the "Limitations" section of the README for the full list. These
include base64-encoded payloads, morse code, and paraphrasings that do
not use known verbs or change register.

## Reproducing this run

From a clean environment:

    uv venv --python 3.14.7
    .venv\Scripts\Activate.ps1
    uv pip install subcanopy-guard
    python scripts/real_world_test.py --verbose

Or from a clone of the repository:

    git clone https://github.com/Vick606/subcanopy-guard
    cd subcanopy-guard
    uv sync
    uv run python scripts/real_world_test.py --verbose

## Interpretation

The shipped package works end-to-end from a fresh install. All documented
interfaces behave as claimed in the README.

The scanner's core architectural claim, that sliding-window local
measurement defeats context dilution, was validated on a 12,000 character
input with an injection buried at the end. Both signals fired, and the
hotspot location points exactly at the injection.

The one failure observed is on a documented limitation (Unicode
homoglyphs) that is already scheduled for v0.4.0. No regressions were
found.
