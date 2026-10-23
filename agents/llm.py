"""The model boundary: every model call in the Why Engine goes through a `Model`.

Live calls go to gpt-5-mini through Microsoft Foundry with Agent Framework and the default
Azure credential. A `Recording` saves each exchange as a fixture; tests and CI use `Replay`
and never call a model (CLAUDE.md). A fixture is keyed by a hash of the role, instructions,
prompt and answer schema, so a changed prompt fails loudly until it is re-recorded.
"""

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, TypeVar

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from azure.identity import DefaultAzureCredential
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)
MAX_TEXT_TOKENS = 8000  # the verifier's whole reply: its checks, then the JSON


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0

    def __add__(self, other: "Usage") -> "Usage":
        return Usage(
            self.input_tokens + other.input_tokens, self.output_tokens + other.output_tokens
        )


class Model(Protocol):
    async def ask(
        self, role: str, instructions: str, prompt: str, schema: type[T]
    ) -> tuple[T, Usage]: ...


class MissingFixture(LookupError):
    pass


def fixture_key(role: str, instructions: str, prompt: str, schema: type[BaseModel]) -> str:
    text = json.dumps([role, instructions, prompt, schema.__name__])
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def last_json[T: BaseModel](text: str, schema: type[T]) -> T:
    """The last JSON object in a reply that writes its reasoning before its answer."""
    end = text.rfind("}")
    for start in [i for i, c in enumerate(text[: end + 1]) if c == "{"]:
        try:
            return schema.model_validate_json(text[start : end + 1])
        except ValueError:
            continue
    raise ValueError(f"no {schema.__name__} in the reply: {text[-200:]!r}")


@dataclass
class FoundryModel:
    """A deployment on the Foundry project: gpt-5-mini for the agents, which honours a
    response schema, or the Verifier's model (`structured=False`), which is asked for JSON
    in the prompt and parsed from its reply."""

    project_endpoint: str
    deployment: str
    structured: bool = True
    _client: FoundryChatClient | None = None

    @classmethod
    def from_env(cls) -> "FoundryModel":
        return cls(
            os.environ["AZURE_FOUNDRY_PROJECT_ENDPOINT"], os.environ["AZURE_OPENAI_DEPLOYMENT"]
        )

    async def ask(
        self, role: str, instructions: str, prompt: str, schema: type[T]
    ) -> tuple[T, Usage]:
        if self._client is None:
            credential = DefaultAzureCredential(
                managed_identity_client_id=os.getenv("AZURE_CLIENT_ID")
            )
            self._client = FoundryChatClient(
                project_endpoint=self.project_endpoint, model=self.deployment, credential=credential
            )
        if self.structured:
            agent = Agent(self._client, instructions=instructions, name=role)
            response = await agent.run(prompt, options={"response_format": schema})
            value = response.value if response.value is not None else response.text
            answer = value if isinstance(value, schema) else schema.model_validate_json(str(value))
            return answer, _usage(response)
        shape = json.dumps(schema.model_json_schema())
        agent = Agent(
            self._client,
            instructions=f"{instructions}\n\nEnd your reply with one JSON object matching this "
            f"schema, and nothing after it:\n{shape}",
            name=role,
        )
        total = Usage()
        for _ in range(2):  # one retry for a reply with no parsable answer
            response = await agent.run(prompt, options={"max_tokens": MAX_TEXT_TOKENS})
            total = total + _usage(response)
            try:
                return last_json(response.text, schema), total
            except ValueError as exc:
                failure = exc
        raise failure


def _usage(response) -> Usage:
    usage = response.usage_details or {}
    return Usage(
        int(usage.get("input_token_count") or 0), int(usage.get("output_token_count") or 0)
    )


@dataclass
class Recording:
    """Calls `model` and saves each exchange under `folder`, for replay in tests."""

    model: Model
    folder: Path

    async def ask(
        self, role: str, instructions: str, prompt: str, schema: type[T]
    ) -> tuple[T, Usage]:
        Path(self.folder).mkdir(parents=True, exist_ok=True)
        path = Path(self.folder) / f"{fixture_key(role, instructions, prompt, schema)}.json"
        record: dict = {"role": role, "prompt": prompt}
        try:
            answer, usage = await self.model.ask(role, instructions, prompt, schema)
        except ValueError as exc:  # a reply with no answer is recorded too, so replay repeats it
            record["error"] = str(exc)
            path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
            raise
        record["answer"] = answer.model_dump(mode="json")
        record["usage"] = {"input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens}
        path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        return answer, usage


@dataclass
class Replay:
    """Answers from recorded fixtures only; a question never recorded is an error."""

    folder: Path

    async def ask(
        self, role: str, instructions: str, prompt: str, schema: type[T]
    ) -> tuple[T, Usage]:
        key = fixture_key(role, instructions, prompt, schema)
        path = Path(self.folder) / f"{key}.json"
        if not path.exists():
            raise MissingFixture(f"no recorded answer for {role} ({key}); re-record the case")
        record = json.loads(path.read_text(encoding="utf-8"))
        if "error" in record:
            raise ValueError(record["error"])
        return schema.model_validate(record["answer"]), Usage(**record["usage"])
