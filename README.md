# Subcanopy Guard

Context-aware indirect prompt injection scanner for AI agent tool outputs.

**Status:** v0.1.0 — in development. The detection engine is under construction. Benchmark results will be published when the scanner is complete.

## The problem

The `buried-injections` benchmark showed that the best transformer detector catches 100% of injection attacks alone but only 23% when the attack is buried inside ordinary tool output. This is *context dilution*: the injection signal is washed out by surrounding benign text. Regex-based detectors catch 0% of buried attacks.

## The approach

Sliding-window instruction density and stylometric discontinuity, combined with provenance-aware taint scoring. Structurally immune to context dilution because the signal is measured locally, not globally.

## License

AGPL-3.0-or-later for the Community Edition. Commercial licensing available for organizations that cannot comply with AGPL. See [COMMERCIAL_LICENSE.md](COMMERCIAL_LICENSE.md).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). All contributors must sign the [CLA](CLA.md).
