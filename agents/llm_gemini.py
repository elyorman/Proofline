"""The agents on Gemini, to compare models (the `experiments` dependency group). The product's
agents run on Microsoft Foundry; this has the same interface as `agents.llm.FoundryModel`.

The key comes from the environment (GEMINI_API_KEY), never from code. The reply is constrained
to the schema and parsed into it; a reply that is not counts as no answer, as on Foundry.
"""

import asyncio
from dataclasses import dataclass

from google import genai
from google.genai import types
from pydantic import BaseModel

from agents.llm import Usage

TIMEOUT_S = 180  # one reply; a thinking model takes longer than a small one


@dataclass
class GeminiModel:
    model: str = "gemini-pro-latest"
    _client: genai.Client | None = None

    async def ask[T: BaseModel](
        self, role: str, instructions: str, prompt: str, schema: type[T]
    ) -> tuple[T, Usage]:
        if self._client is None:
            self._client = genai.Client()
        config = types.GenerateContentConfig(
            system_instruction=instructions,
            response_mime_type="application/json",
            response_schema=schema,
        )
        try:
            response = await asyncio.wait_for(
                self._client.aio.models.generate_content(
                    model=self.model, contents=prompt, config=config
                ),
                TIMEOUT_S,
            )
        except TimeoutError as exc:
            raise ValueError(f"no {schema.__name__} within {TIMEOUT_S} s") from exc
        answer = response.parsed
        if not isinstance(answer, schema):
            raise ValueError(f"no {schema.__name__} in the reply")
        meta = response.usage_metadata
        spent = (meta.candidates_token_count or 0) + (meta.thoughts_token_count or 0)
        return answer, Usage(meta.prompt_token_count or 0, spent)
