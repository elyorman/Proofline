"""Which model the agents run on. Constructing a model calls nothing."""

import pytest

from orchestration.case import _agents


def test_the_agents_run_on_foundry_unless_a_comparison_names_another_family(monkeypatch):
    monkeypatch.setenv("PROOFLINE_AGENT_MODEL", "llama:big")
    with pytest.raises(ValueError, match="unknown agent model"):
        _agents()
    pytest.importorskip("anthropic")  # the experiments group
    monkeypatch.setenv("PROOFLINE_AGENT_MODEL", "claude:claude-opus-5-5")
    assert _agents().model == "claude-opus-5-5"
    pytest.importorskip("google.genai")
    monkeypatch.setenv("PROOFLINE_AGENT_MODEL", "gemini:")
    assert _agents().model == "gemini-pro-latest"
