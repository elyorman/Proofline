"""Which model the agents run on. Constructing a model calls nothing."""

import pytest

from orchestration.case import _agents


def test_the_agents_run_on_foundry_unless_a_comparison_names_another_family(monkeypatch):
    monkeypatch.setenv("PROOFLINE_AGENT_MODEL", "llama:big")
    with pytest.raises(ValueError, match="unknown agent model"):
        _agents()
    pytest.importorskip("anthropic")  # the experiments group
    monkeypatch.setenv("PROOFLINE_AGENT_MODEL", "claude:claude-opus-5-5")
    assert (_agents().model, _agents().effort) == ("claude-opus-5-5", "medium")
    monkeypatch.setenv("PROOFLINE_AGENT_MODEL", "claude:claude-opus-5-5@high")
    assert _agents().effort == "high"
    pytest.importorskip("google.genai")
    monkeypatch.setenv("PROOFLINE_AGENT_MODEL", "gemini:")
    assert _agents().model == "gemini-pro-latest"


def test_a_dropped_connection_is_retried_and_a_model_error_is_not(monkeypatch):
    import asyncio

    from agent_framework.exceptions import ChatClientException

    from agents import llm

    real_sleep = asyncio.sleep
    monkeypatch.setattr(llm.asyncio, "sleep", lambda s: real_sleep(0))

    class Flaky:
        def __init__(self, failures, message):
            self.failures, self.message, self.calls = failures, message, 0

        async def run(self, prompt, options):
            self.calls += 1
            if self.calls <= self.failures:
                raise ChatClientException(self.message)
            return "answer"

    dropped = Flaky(2, "service failed to complete the prompt: Connection error.")
    assert asyncio.run(llm._run(dropped, "p", {}, llm.Usage)) == "answer" and dropped.calls == 3
    refused = Flaky(1, "content filter")
    with pytest.raises(ChatClientException):
        asyncio.run(llm._run(refused, "p", {}, llm.Usage))
    assert refused.calls == 1
