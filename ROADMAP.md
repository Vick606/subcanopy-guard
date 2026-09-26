<div align="center">

# Roadmap

**Where Subcanopy Guard is going, and what is deliberately out of scope.**

</div>

---

## [x] v0.3.1 - Current (September 2026)

- Prompt-exfiltration phrases: `system prompt`, `your (exact|original)? instructions`, `word for word`, `verbatim`
- Harmful-content framing: `(harmful|dangerous|malicious|illegal|unsafe) (instructions|content|acts)`
- `act as` broadened to accept `(if|a|an|my|the)` for persona hijacks
- `repeat` promoted from REGULAR to STRONG weight
- **PromptWall:** 45.1% overall @ 0% FP
- **AgentDojo v1:** 86.5% caught @ 5.2% FP at CRITICAL, 0.85 ms
- Test suite: 126 passing

## [x] v0.3.0 - Shipped (September 2026)

- Phrase-matching layer for jailbreak, persona-hijack, and instruction-override patterns
- STRONG verb weight raised from 1.0 to 1.5
- **PromptWall:** 34.7% overall @ 0% FP
- **AgentDojo v1:** 86.5% caught @ 5.2% FP at CRITICAL

## [x] v0.2.0 - Shipped (September 2026)

- Sliding-window instruction density signal (~60-verb lexicon)
- Stylometric discontinuity signal (adjacent-sentence delta)
- Provenance-aware risk multipliers
- Availability rule: unavailable signals don't dilute available ones
- CLI `scg scan` with file, stdin, JSON output, and provenance flags
- `protect()` decorator for Python integrations

## [ ] v0.4.0 - Planned (Q1 2027)

**Focus: handle obfuscation.**

- Optional decoding layer for base64, morse, and unicode homoglyphs
- Two-stage scan: fast first pass, then decode-and-rescan only when a decode pattern is detected
- Opt-in via `scg scan --decode` (default off)

**Expected impact:** PromptWall `encoded_attack` 20.5% -> 50%+.

## [ ] v0.5.0 - Planned

**Focus: production readiness.**

- Streaming scanner (`scg watch` on a file, socket, or HTTP endpoint)
- Structured output formats: SARIF, JSONL, CSV
- Integration examples for LangChain, CrewAI, and the OpenAI Agents SDK
- Response scanning (post-LLM output for data leakage)

## [ ] v1.0.0 - Planned

- Stable API guarantee
- Commercial Edition: SSO, audit logs, compliance reporting (NIST AI RMF / ISO 42001)
- Published calibration tool for tuning thresholds on your own corpus

## [-] Not planned

**ML-based classification.** Excellent transformer detectors already exist (`protectai-deberta-v2`, `llm-guard`, Prompt Guard 2). Subcanopy Guard is deliberately the fast, dependency-free, context-aware layer that complements them - not a replacement.

---

<div align="center">

<sub>Have a feature request? Open an [issue](https://github.com/Vick606/subcanopy-guard/issues) - the roadmap is shaped by what users actually need.</sub>

</div>
