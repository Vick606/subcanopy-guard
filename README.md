<div align="center">

# Subcanopy Guard

**Context-aware indirect prompt injection scanner for AI agent tool outputs.**

Fast, dependency-free, and built to catch what whole-sequence classifiers miss.

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](LICENSE)
[![Python 3.14+](https://img.shields.io/badge/python-3.14+-3776AB?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-126_passing-brightgreen.svg)](#)
[![AgentDojo](https://img.shields.io/badge/AgentDojo-86.5%25_@_5.2%25_FP-8A2BE2)](#results)
[![PromptWall](https://img.shields.io/badge/PromptWall-45.1%25_@_0%25_FP-blueviolet)](#results)
[![p50](https://img.shields.io/badge/p50-0.85_ms-orange)](#results)

</div>

---

## The problem

The [`buried-injections`](https://github.com/rudratoshs/buried-injections) benchmark ran 10 open-source prompt-injection detectors against **629 real [AgentDojo](https://github.com/ethz-spylab/agentdojo) attacks**, each embedded inside ordinary tool output — the way an agent firewall actually sees them.

The best detector caught **51%**. Meta's Prompt Guard 2 caught **1%**. A regex baseline caught **0%**.

The reason is **context dilution**: the same attack that a classifier catches with 100% accuracy on its own drops to 23% when surrounded by benign text. Whole-sequence transformers see one big input and the injection signal gets washed out.

## The approach

Subcanopy Guard attacks the problem from a different angle. Instead of classifying the whole text at once, it slides a window across the input and measures **local instruction density** — the concentration of imperative verbs and jailbreak phrases within that window. It then layers on two more signals:

- 🧠 **Density** — imperative-verb and phrase concentration in a sliding window
- 📐 **Discontinuity** — style breaks between adjacent sentences
- 🎯 **Provenance** — risk multiplier by source (tool output, retrieved doc, user input, system prompt)

No ML models. No external API calls. Pure Python standard library. **Sub-millisecond scans.**

---

## Results

### AgentDojo v1 — 629 attacks buried in tool output, 97 benign

| Threshold | Caught | False positives | p50 |
|---|---|---|---|
| **CRITICAL** | **544/629 (86.5%)** | **5/97 (5.2%)** | **0.85 ms** |
| HIGH | 629/629 (100%) | 11/97 (11.3%) | 0.67 ms |

### Comparison to published baselines on the same corpus

| Detector | Caught | FP | p50 |
|---|---|---|---|
| regex-baseline | 0% | 0% | 0.05 ms |
| Meta Prompt Guard 2 (86M) | 1% | 0% | 149 ms |
| llm-guard | 20% | 2% | 124 ms |
| protectai-deberta-v2 | 23% | 4% | 163 ms |
| jailbreak-detector-large | 51% | 2% | 110 ms |
| **subcanopy-guard (CRITICAL)** | **86.5%** | **5.2%** | **0.85 ms** |

<sub>Baselines from [`rudratoshs/buried-injections`](https://github.com/rudratoshs/buried-injections). All detectors evaluated on CPU. At `--block-at CRITICAL` we beat the paper's leader by 35 points at comparable false-positive rate and ~130× lower latency.</sub>

### PromptWall — 430 attacks, 8 categories, 70 safe prompts

The **generalization test**: 8 different attack families with distinct templates, not one. Direct user input, `source=user_input`.

| Category | Caught | Rate |
|---|---|---|
| multi_turn_drift | 23/35 | 65.7% |
| prompt_exfiltration | 28/51 | 54.9% |
| indirect_injection | 25/46 | 54.3% |
| social_engineering | 21/42 | 50.0% |
| direct_injection | 44/95 | 46.3% |
| jailbreak | 28/74 | 37.8% |
| persona_hijacking | 16/43 | 37.2% |
| encoded_attack | 9/44 | 20.5% |
| **Overall** | **194/430** | **45.1%** |

**False positives: 0/70 (0%).** p50 latency: 0.09 ms.

<sub>Dataset: [`cyberec/promptwall-injection-dataset`](https://huggingface.co/datasets/cyberec/promptwall-injection-dataset). Overall recall has more than tripled from v0.2.0 (14.7% → 45.1%) with zero false positives. Remaining gap is encoded attacks (base64, homoglyphs), scheduled for v0.4.0 — see [ROADMAP.md](ROADMAP.md).</sub>

---

## Install

```bash
pip install subcanopy-guard
```

## Quick start

### CLI

```bash
scg scan tool_output.json          # scan a file
scg scan -                         # read from stdin
cat response.txt | scg scan -      # pipe from another tool
scg scan --json suspicious.txt     # structured output for CI
scg scan --source retrieved_doc doc.txt
scg scan --block-at MEDIUM file.txt
```

Exit codes: **0** clean · **1** blocked · **2** usage/file error. Drop-in for CI pipelines and pre-tool-call gates.

### Python

```python
from subcanopy_guard import ContextScanner

scanner = ContextScanner(source="tool_output")
result = scanner.scan(tool_response)

if result.severity in ("HIGH", "CRITICAL"):
    log.warning("blocked: %s at %s", result.matches, result.hotspots)
```

Or as a decorator:

```python
@scanner.protect(arg_name="tool_result")
def process(tool_result: str) -> str:
    ...  # raises InjectionRiskError if the scan blocks
```

---

## How it works

Three signals, combined.

### 1. Density — sliding window over imperatives and phrases

Two scoring layers feed a sliding 25-token window with 10-token stride:

- **Token layer.** A ~60-verb lexicon with two tiers. STRONG verbs (`ignore`, `disregard`, `jailbreak`, `override`, `repeat`) weigh 1.5; REGULAR verbs (`print`, `execute`, `act`, `send`) weigh 0.5.
- **Phrase layer.** Multi-word patterns (`developer mode`, `system prompt`, `no restrictions`, `DAN`, `ignore all previous`, `act as`, `pretend you are`, `word for word`) contribute their weight once per occurrence to the first overlapping token.

Window score is `min(weighted / 2.0, 1.0)`. The highest window score is the density risk. A single STRONG verb or a single jailbreak phrase pushes a window to HIGH on its own.

**Why it defeats context dilution:** the window measures *local* concentration, not *global* presence. An injection buried in 500 tokens of benign JSON still produces a localized spike that the window catches.

### 2. Discontinuity — adjacent-sentence style delta

Split on sentence-ending punctuation, JSON structural characters, and commas. Extract two features per sentence: second-person pronoun density and imperative verb density. Compute the L1 distance between adjacent sentences. The maximum delta is the discontinuity risk.

**Why it works:** benign tool output is declarative and third-person. Injection voice is imperative and second-person. The *transition* between them is the signal, even when either sentence alone looks benign.

### 3. Provenance — source-aware multiplier

| Source | Multiplier | Meaning |
|---|---|---|
| `system_prompt` | 0.5× | Developer-controlled |
| `user_input` | 1.0× | Baseline |
| `retrieved_doc` | 1.3× | RAG chunks |
| `tool_output` | 1.5× | External service responses |

### Combination

```text
if both signals available:
    base = 0.6 * density + 0.4 * discontinuity
    if both > 0.3:
        base *= 1.15                # agreement bonus
elif only density available:
    base = density
elif only discontinuity available:
    base = discontinuity
else:
    base = 0.0

final    = min(base * provenance_multiplier, 1.0)
severity = classify(final)
```

**Availability rule:** a signal that cannot be computed (input too short) does not vote against a signal that can. This matters for single-sentence injections where discontinuity has no adjacent sentences to compare against.

Severity bands: `CLEAN < 0.15` · `LOW < 0.35` · `MEDIUM < 0.55` · `HIGH < 0.75` · `CRITICAL ≥ 0.75`.

---

## Limitations

This is a **heuristic detector**, not a classifier. It is deliberately complementary to transformer-based scanners, not a replacement.

**Good at:**

- ✅ Template-based indirect injection buried in tool output (AgentDojo)
- ✅ Distinguishing injection register from tool-output register
- ✅ Recognising jailbreak, persona-hijack, and prompt-exfiltration vocabulary
- ✅ Running fast enough for per-tool-call scanning in production

**Weak at:**

- ❌ **Encoded attacks** — base64, morse, unicode homoglyphs are not decoded (v0.4.0)
- ❌ **Paraphrased attacks** that don't change register or use known verbs
- ❌ **Sophisticated social engineering** — polite, embedded, indistinguishable from benign requests
- ❌ **Attacks relying on procedural knowledge** rather than vocabulary

**Known false positives on AgentDojo v1:** 5/97 (5.2%) at `--block-at CRITICAL`. The v0.3.0 phrase layer introduced 2 additional false positives (3/97 → 5/97) in exchange for a large recall gain on the PromptWall generalization benchmark. Tradeoff documented; tracked for a future tuning pass.

> ⚠️ **Do not use Subcanopy Guard as your only defense.** It is a fast pre-filter. Pair it with a transformer classifier for direct injection and with taint-tracking for agent tool-call security.

---

## Performance

| | |
|---|---|
| Per-scan latency | 0.09–0.85 ms |
| ML models | None |
| Runtime dependencies | None |
| Python | 3.14+ |

Compare to the fastest transformer detector (`fmops-distilbert`, 31 ms) — Subcanopy Guard is ~40–150× faster, but trades recall on encoded and socially-engineered attacks for that speed. That tradeoff is deliberate.

---

## License

Dual-licensed:

| Edition | License | Audience |
|---|---|---|
| **Community** | AGPL-3.0-or-later | Open-source, research, AGPL-compatible |
| **Commercial** | Proprietary | Organizations embedding in closed-source products |

See [COMMERCIAL_LICENSE.md](COMMERCIAL_LICENSE.md) for commercial terms and [CLA.md](CLA.md) for the contributor agreement.

---

## Contributing

All contributions require a signed [CLA](CLA.md). See [CONTRIBUTING.md](CONTRIBUTING.md) for the development setup.

## Roadmap

See [ROADMAP.md](ROADMAP.md). Highlights:

- **v0.3.0** — lexicon expansion for jailbreak and persona attacks ✅ shipped
- **v0.3.1** — prompt-exfiltration phrases ✅ shipped
- **v0.4.0** — optional decoding layer for base64 and homoglyphs
- **v0.5.0** — streaming scanner and framework integrations

## Acknowledgments

Built on the findings of the [`buried-injections`](https://github.com/rudratoshs/buried-injections) benchmark. The discontinuity signal is inspired by the stylometric approach described in *"Beyond Pattern Matching"* (April 2026). The severity band model follows ASCEND and `tester311249/llm-security`.

---

<div align="center">

**Built with ☕ and ❤️ by [Victor](https://github.com/Vick606) 🐍**

<sub>If Subcanopy Guard saves you time, consider starring the repo or opening an issue with feedback.</sub>

</div>
