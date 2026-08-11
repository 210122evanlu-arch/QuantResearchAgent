"""Provider-independent structured output interface."""

from typing import Protocol, TypeVar

from pydantic import BaseModel

SchemaT = TypeVar("SchemaT", bound=BaseModel)


class StructuredLLM(Protocol):
    """Minimal interface required by all LLM-backed graph nodes."""

    def generate(
        self,
        *,
        schema: type[SchemaT],
        system_prompt: str,
        user_prompt: str,
        node_name: str,
    ) -> SchemaT:
        """Return one instance of ``schema`` for the supplied prompts."""
