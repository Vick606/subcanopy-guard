# AGENTS.md

Instructions for AI coding agents (Copilot, Cursor, Claude Code, Codex CLI)
contributing to Subcanopy Guard.

A context-aware indirect prompt injection scanner for AI agent tool outputs.
Heuristic detector, not a classifier. Zero runtime dependencies.

## Accountability

**A human submitter must understand and defend every changed line.** Pure
code-agent PRs are not allowed. The human must review the diff and run the
tests. If the work is duplicative or trivial busywork, do not proceed.

## Commits

- Conventional commits: `feat:`, `fix:`, `docs:`, `test:`, `chore:`,
  `refactor:`. One logical change per commit.
- Explain *why* in the body, not *what*. The diff shows the what.
- AI attribution when applicable: `Co-authored-by: GitHub Copilot`

## License headers

Every `.py` file starts with an SPDX header. Copy the existing block from
any source file. Do not add SPDX headers to markdown or YAML.

## Testing

- Every behavior change needs a test in `tests/`.
- Run before committing:

      uv run pytest           # all 126 tests must pass
      uv run ruff check .     # zero warnings

## Values that require benchmark measurement

These were tuned against AgentDojo v1 and PromptWall. Changing any of them
requires re-running both benchmarks and documenting the impact in the commit.

| Setting | Value |
|---|---|
| `window_tokens` / `stride_tokens` | 25 / 10 |
| `target_count` | 2.0 |
| `STRONG` / `REGULAR` weights | 1.5 / 0.5 |
| `density_weight` / `discontinuity_weight` | 0.6 / 0.4 |
| Agreement bonus | 1.15 (when both signals > 0.3) |
| Provenance multipliers | tool_output 1.5, retrieved_doc 1.3, user_input 1.0, system_prompt 0.5 |

## What not to do

- **Do not add runtime dependencies.** Zero is a feature. Benchmark-only
  deps go in the `bench` group.
- **Do not propose ML-based classification.** We complement transformer
  detectors, not replace them. See ROADMAP.md "Not planned."
- **Do not catch broad exceptions.** No `except Exception`, no bare `except:`.
- **Do not reformat unrelated files.** Keep the diff focused.

## CLA

All external contributions require a signed [CLA](CLA.md). Agents cannot
sign it — the human must complete it before the PR can be merged.
