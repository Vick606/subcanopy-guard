# Security Policy

## Supported Versions

| Version | Supported | Notes |
|---|---|---|
| 0.3.x | ✅ Active | Current release. Security fixes and improvements. |
| 0.2.x | ⚠️ Critical fixes only | Upgrade to 0.3.x recommended. |
| < 0.2.0 | ❌ Not supported | Pre-release scaffolding. |

## Reporting a Vulnerability

**Do not open a public issue for security vulnerabilities.**

Report privately using one of these channels:

1. **GitHub Security Advisories** (preferred):
   https://github.com/Vick606/subcanopy-guard/security/advisories/new

2. **Email:** `security@subcanopyguard.dev`

Include:

- A description of the vulnerability and its impact
- Steps to reproduce (a minimal input that triggers the issue)
- The version of Subcanopy Guard affected
- Any suggested fix, if you have one
- Whether you plan to disclose publicly and on what timeline

## What to Expect

| Stage | Target |
|---|---|
| Acknowledge receipt | Within 72 hours |
| Initial triage and severity assessment | Within 7 days |
| Fix or mitigation available | Within 30 days for HIGH/CRITICAL |
| Coordinated public disclosure | Within 90 days of the report |

If a fix takes longer than 30 days, we will keep you updated on progress. We will credit you in the advisory and the changelog unless you ask to remain anonymous.

## Scope

Subcanopy Guard is a **heuristic prompt-injection scanner**. It is deliberately not a classifier, and its known limitations are documented in the README. The following are **not** considered security vulnerabilities:

- **Encoded attacks** (base64, morse, unicode homoglyphs). Not decoded; planned for v0.4.0.
- **Prompt-exfiltration phrasing** not yet in the lexicon. The lexicon expands over time.
- **Paraphrased injections** that don't change register or use known verbs.
- **Sophisticated social-engineering attacks** that read as benign.
- **False negatives on any specific input.** No detector catches everything. The benchmark numbers in the README are the honest baseline.

A genuine vulnerability is something that breaks a documented guarantee — for example:

- A crash or unhandled exception from crafted input
- ReDoS in a regex pattern
- Infinite loop or unbounded memory growth
- Output that misrepresents a scan result (e.g., reports CLEAN when it should report HIGH)
- A bypass of the `protect()` decorator that lets a scan return without raising
- Any issue in the `commercial` edition (private repo)

## False Positive Reports

A false positive (benign text scored as HIGH or CRITICAL) is not a vulnerability, but it is a real quality issue. Open a public issue with the text that triggered it, the `--source` value used, and the scan output. We track false positives in the benchmarks and use them to tune the signals.

## Dependencies

Subcanopy Guard has **zero runtime dependencies**. The `bench` group (agentdojo, langchain, etc.) is used only for benchmark runs and is not installed by end users. Supply-chain risk in the shipped package is therefore minimal.

## Disclosure Policy

We follow **coordinated disclosure**. If you report a vulnerability and we fix it, we will:

1. Publish a GitHub Security Advisory
2. Credit you in the advisory and the changelog
3. Release a patch version with the fix
4. Not disclose details before a fix is available

If you disclose publicly before a fix is available, we will still work on the fix, but we cannot coordinate the messaging and the credit process.
