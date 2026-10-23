"""The agents on Claude, to compare models (the `experiments` dependency group). The product's
agents run on Microsoft Foundry; this has the same interface as `agents.llm.FoundryModel`.

The key comes from the environment (ANTHROPIC_API_KEY), never from code. Replies are
schema-validated by the API (structured outputs); refused requests fall back server-side
to another model, and a reply that still has no answer counts as none, as on Foundry.
"""

import asyncio
from dataclasses import dataclass

import anthropic
from pydantic import BaseModel

from agents.llm import Usage

TIMEOUT_S = 180  # one reply; thinking at high effort takes longer than a small model


@dataclass
class ClaudeModel:
    model: str = "claude-opus-5-5"
    effort: str = "high"  # reasoning about causes is the hard part of the job
    _client: anthropic.AsyncAnthropic | None = None

    async def ask[T: BaseModel](
        self, role: str, instructions: str, prompt: str, schema: type[T]
    ) -> tuple[T, Usage]:
        if self._client is None:
            self._client = anthropic.AsyncAnthropic()
        try:
            response = await asyncio.wait_for(
                self._client.beta.messages.parse(
                    model=self.model,
                    max_tokens=16000,
                    system=instructions,
                    messages=[{"role": "user", "content": prompt}],
                    output_format=schema,
                    output_config={"effort": self.effort},
                    cache_control={"type": "ephemeral"},  # role instructions repeat per case
                    betas=["server-side-fallback-2026-07-01"],
                    fallbacks="default",
                ),
                TIMEOUT_S,
            )
        except TimeoutError as exc:
            raise ValueError(f"no {schema.__name__} within {TIMEOUT_S} s") from exc
        if response.stop_reason == "refusal" or response.parsed_output is None:
            raise ValueError(f"no {schema.__name__} in the reply ({response.stop_reason})")
        usage = Usage(response.usage.input_tokens, response.usage.output_tokens)
        return response.parsed_output, usage
