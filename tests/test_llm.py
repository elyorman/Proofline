"""The model client's behaviour on a dropped connection; nothing here calls a live model."""

import pytest


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
