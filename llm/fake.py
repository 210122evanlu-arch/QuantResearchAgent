"""Deterministic offline structured LLM for unit tests."""

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from llm.errors import StructuredOutputError
from llm.protocol import SchemaT


@dataclass(frozen=True)
class FakeLLMCall:
    schema_name: str
    node_name: str
    system_prompt: str
    user_prompt: str


class FakeStructuredLLM:
    """Return queued fixtures while preserving the production client contract."""

    def __init__(self, responses: dict[type[BaseModel], Any | list[Any]]) -> None:
        self._responses: dict[type[BaseModel], deque[Any]] = defaultdict(deque)
        for schema, response in responses.items():
            queued = response if isinstance(response, list) else [response]
            self._responses[schema].extend(queued)
        self.calls: list[FakeLLMCall] = []

    def generate(
        self,
        *,
        schema: type[SchemaT],
        system_prompt: str,
        user_prompt: str,
        node_name: str,
    ) -> SchemaT:
        self.calls.append(
            FakeLLMCall(
                schema_name=schema.__name__,
                node_name=node_name,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
        )

        if not self._responses[schema]:
            raise StructuredOutputError(
                f"No fake response configured for schema {schema.__name__}"
            )

        response = self._responses[schema].popleft()
        if isinstance(response, schema):
            return response

        return schema.model_validate(response)
