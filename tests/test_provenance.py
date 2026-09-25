# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Victor

"""Tests for the provenance taint adjustment."""

from __future__ import annotations

import pytest

from subcanopy_guard import provenance


class TestAdjust:
    def test_tool_output_amplifies(self) -> None:
        result = provenance.adjust(0.4, "tool_output")
        assert result.risk == pytest.approx(0.6)
        assert result.multiplier == 1.5

    def test_system_prompt_dampens(self) -> None:
        result = provenance.adjust(0.4, "system_prompt")
        assert result.risk == pytest.approx(0.2)
        assert result.multiplier == 0.5

    def test_user_input_is_baseline(self) -> None:
        result = provenance.adjust(0.4, "user_input")
        assert result.risk == pytest.approx(0.4)
        assert result.multiplier == 1.0

    def test_retrieved_doc_amplifies_less_than_tool_output(self) -> None:
        doc = provenance.adjust(0.4, "retrieved_doc")
        tool = provenance.adjust(0.4, "tool_output")
        assert doc.risk < tool.risk

    def test_unknown_source_uses_default(self) -> None:
        result = provenance.adjust(0.4, "some_mystery_source")
        assert result.risk == pytest.approx(0.4)
        assert result.multiplier == 1.0

    def test_output_is_clamped_to_one(self) -> None:
        result = provenance.adjust(0.9, "tool_output")
        assert result.risk == 1.0

    def test_input_is_clamped_to_zero(self) -> None:
        result = provenance.adjust(-0.5, "tool_output")
        assert result.risk == 0.0

    def test_source_is_preserved(self) -> None:
        result = provenance.adjust(0.4, "tool_output")
        assert result.source == "tool_output"


class TestConfig:
    def test_custom_multipliers(self) -> None:
        cfg = provenance.ProvenanceConfig(
            multipliers={"internal": 0.1},
            default_multiplier=2.0,
        )
        trusted = provenance.adjust(0.5, "internal", cfg)
        unknown = provenance.adjust(0.5, "external", cfg)
        assert trusted.risk == pytest.approx(0.05)
        assert unknown.risk == pytest.approx(1.0)

    def test_known_sources_lists_defaults(self) -> None:
        sources = provenance.known_sources()
        assert "tool_output" in sources
        assert "system_prompt" in sources
        assert "user_input" in sources
        assert "retrieved_doc" in sources

    def test_config_does_not_share_state(self) -> None:
        cfg_a = provenance.ProvenanceConfig()
        cfg_b = provenance.ProvenanceConfig()
        cfg_a.multipliers["tool_output"] = 99.0
        assert cfg_b.multipliers["tool_output"] == 1.5
