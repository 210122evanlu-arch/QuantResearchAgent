"""Reusable implementation for schema-producing graph nodes."""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from llm.protocol import StructuredLLM
from schemas.state import ResearchState

OutputT = TypeVar("OutputT", bound=BaseModel)


class NodeInputError(ValueError):
    """Raised when a graph node is invoked without required state artifacts."""


def _json_compatible(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return value


@dataclass(frozen=True)
class StructuredNode(Generic[OutputT]):
    """Convert selected state fields into one validated Pydantic output."""

    name: str
    output_key: str
    output_schema: type[OutputT]
    input_keys: tuple[str, ...]
    system_prompt: str
    llm: StructuredLLM

    def __call__(self, state: ResearchState) -> dict:
        state_values: Mapping[str, Any] = state
        missing = [key for key in self.input_keys if key not in state_values]
        if missing:
            joined = ", ".join(missing)
            raise NodeInputError(
                f"Node {self.name!r} is missing state fields: {joined}"
            )

        inputs = {key: _json_compatible(state_values[key]) for key in self.input_keys}
        user_prompt = (
            "Generate the required structured output from these verified state "
            "artifacts. Do not add facts that are not supported by the input.\n\n"
            + json.dumps(inputs, ensure_ascii=False, indent=2, default=str)
        )
        output = self.llm.generate(
            schema=self.output_schema,
            system_prompt=self.system_prompt,
            user_prompt=user_prompt,
            node_name=self.name,
        )
        return {
            self.output_key: output,
            "current_stage": self.name,
        }
