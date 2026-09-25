# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `SECURITY.md`: vulnerability disclosure policy with supported versions,
  private reporting channels, response SLA, and out-of-scope items
- `CODE_OF_CONDUCT.md`: Contributor Covenant v2.1

## [0.3.0] - 2026-09-25

### Added

- Phrase-matching layer in the density signal. Multi-word patterns covering
  jailbreak (`developer mode`, `DAN`, `no restrictions`), persona hijacking
  (`act as`, `pretend you are`, `roleplay as`), and instruction override
  (`ignore all previous`, `disregard`, `forget all previous`).
- New test classes: `TestTokenWeight`, `TestPhraseWeights`, `TestPhraseScore`
  in `tests/test_density.py`; `TestJailbreakDetection` in `tests/test_scanner.py`.
- `ROADMAP.md`: public roadmap covering v0.3.0 through v1.0.0.

### Changed

- **STRONG verb weight raised from 1.0 to 1.5.** A single STRONG verb now
  scores 0.75 on its own (`1.5 / 2.0`), crossing the HIGH threshold. Previously
  a single STRONG verb scored 0.5 (MEDIUM), which let single-sentence
  injections through.
- README updated with v0.3.0 benchmark results and refreshed badges.

### Results

- **PromptWall**: 14.7% → **34.7%** overall at 0% false positives
  - `multi_turn_drift`: 22.9% → 60.0%
  - `social_engineering`: 9.5% → 38.1%
  - `jailbreak`: 8.1% → 36.5%
  - `persona_hijacking`: 4.7% → 34.9%
  - `indirect_injection`: 34.8% → 47.8%
  - `direct_injection`: 22.1% → 38.9%
- **AgentDojo v1**: unchanged at 86.5% caught (CRITICAL). False positives
  3.1% → 5.2% (documented tradeoff for the phrase layer).
- Test suite: **111 passing**.

## [0.2.0] - 2026-09-25

### Added

- **Density signal** (`density.py`): sliding-window instruction density over
  a ~60-verb lexicon with STRONG (1.0) and REGULAR (0.5) weights.
- **Discontinuity signal** (`discontinuity.py`): adjacent-sentence stylometric
  delta using second-person pronoun density and imperative verb density.
- **Provenance adjustment** (`provenance.py`): source-aware risk multipliers
  (`tool_output` 1.5×, `retrieved_doc` 1.3×, `user_input` 1.0×,
  `system_prompt` 0.5×).
- **ContextScanner** (`scanner.py`): composes the three signals with a
  weighted sum, agreement bonus, and 5-level severity classification
  (CLEAN/LOW/MEDIUM/HIGH/CRITICAL).
- **CLI** (`cli.py`): `scg scan` with file, stdin, `--json`, `--source`, and
  `--block-at` flags. Exit codes: 0 clean, 1 blocked, 2 usage/file error.
- **`protect()` decorator** for wrapping Python functions that process
  untrusted text.
- **Benchmark infrastructure**: `bench/corpus.py` (AgentDojo v1 corpus loader,
  726 cases), `bench/run.py` (benchmark runner), `bench/diagnose.py`
  (signal-contribution diagnostic), `bench/promptwall.py` (PromptWall
  generalization benchmark), `bench/stats.py` (dataset composition).
- **Availability flag** on `DensityResult` and `DiscontinuityResult`.
- Real `README.md` with benchmark results, architecture explanation, and an
  honest limitations section.
- `ROADMAP.md` covering v0.3.0 through v1.0.0.

### Changed

- Minimal placeholder README replaced with the full product README.

### Fixed

- **Scanner no longer dilutes available signals with unavailable ones.** A
  signal that cannot be computed (e.g. discontinuity on a single sentence)
  was returning 0.0 and acting as a phantom "not malicious" vote. Fixed by
  renormalizing: if only density is available, use density alone; if only
  discontinuity is available, use discontinuity alone; if neither, use 0.0.
  Single-sentence injections now score on density alone.
- `bench/diagnose.py`: explicit `strict=False` on the `zip()` call comparing
  attack and benign strings (ruff B905).

### Results

- **AgentDojo v1**: 86.5% caught at 3.1% false positives (CRITICAL), 0.34 ms.
- **PromptWall**: 14.7% overall at 0% false positives.
- Test suite: **87 passing**.

## [0.1.0-scaffold] - 2026-09-25

### Added

- Initial project scaffolding.
- **Dual licensing structure**: AGPL-3.0-or-later for the Community Edition
  and a Commercial License for organizations that cannot comply with AGPL.
- `LICENSE` (full AGPL-3.0 text), `COMMERCIAL_LICENSE.md`, `CLA.md`,
  `CONTRIBUTING.md`, `.gitignore`.
- `src/` layout with the `subcanopy_guard` package.
- `scg` CLI entry point (placeholder).
- SPDX headers on all source files.
- `pytest` and `ruff` configuration via `uv` dependency groups.
- Empty `tests/` package.

[Unreleased]: https://github.com/Vick606/subcanopy-guard/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/Vick606/subcanopy-guard/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/Vick606/subcanopy-guard/compare/v0.1.0-scaffold...v0.2.0
[0.1.0-scaffold]: https://github.com/Vick606/subcanopy-guard/releases/tag/v0.1.0-scaffold
