# FAQ

## General

### What is Subcanopy Guard?

A context-aware indirect prompt injection scanner for AI agent tool outputs.
It detects injections buried inside tool responses, retrieved documents, and
other untrusted content that agents process.

### How is this different from LLM Guard, Prompt Guard, or Rebuff?

Those are whole-sequence classifiers. They read the entire input at once and
emit a probability. When the input is 500 tokens of benign text with a
20-token injection buried inside, the injection signal gets mathematically
averaged out. Subcanopy Guard slides a window across the input and measures
local instruction density, which is structurally immune to that dilution.

### Is this a replacement for a transformer classifier?

No. It is a fast pre-filter. Use it alongside a transformer classifier for
defense in depth. See the Limitations section of the README for what it
does and does not catch.

## Results and benchmarks

### Why does AgentDojo show 86.5% but PromptWall shows 45.1%?

AgentDojo v1 uses a single attack template, so the scanner benefits from
template detection. PromptWall has 8 different attack families with distinct
templates. The drop to 45.1% is the generalization penalty, and it is the
more honest number for real-world performance. Both are published.

### How do I reproduce the benchmarks?

    uv sync --group bench
    uv run python -m bench.corpus
    uv run python -m bench.run --block-at CRITICAL
    uv run python -m bench.promptwall --per-category

### What about false positives?

5/97 (5.2%) on AgentDojo v1 at CRITICAL. 0/70 (0%) on PromptWall. The false
positives come from the phrase layer, which trades precision for recall on
the harder benchmark. Documented as a deliberate tradeoff.

## Technical

### Why zero runtime dependencies?

So it installs anywhere Python runs. No torch, no transformers, no GPU.
`pip install subcanopy-guard` and it works. This is deliberate — it is a
pre-filter, not a classifier.

### What Python version is required?

Python 3.14+. Uses `importlib.metadata` for version resolution and modern
type syntax.

### Can I use this in a commercial product?

Yes, under the AGPL-3.0, or under a commercial license if AGPL does not fit
your organization. See COMMERCIAL_LICENSE.md.

### Why AGPL instead of MIT?

AGPL ensures that if someone modifies Subcanopy Guard and serves it over a
network, they contribute their changes back. The commercial license exists
for organizations that cannot comply with that. This dual-licensing model
funds continued development.

## Contributing

### Do I need to sign a CLA?

Yes. All external contributions require a signed CLA. See CLA.md.

### How do I report a security vulnerability?

Do not open a public issue. Use the private channel described in SECURITY.md.

### What is planned next?

See ROADMAP.md. v0.4.0 adds a decoding layer for base64 and homoglyphs.
v0.5.0 adds streaming and framework integrations.
