"""Make one small structured call to the configured production LLM."""

from typing import Literal

from pydantic import BaseModel

from config import get_llm_provider
from llm import get_default_llm


class ConnectionCheck(BaseModel):
    status: Literal["ok"]
    message: str


def main() -> None:
    provider = get_llm_provider()
    result = get_default_llm().generate(
        schema=ConnectionCheck,
        system_prompt="Return the requested structured connection check only.",
        user_prompt="Confirm that this model connection works. Set status to ok.",
        node_name="connection_check",
    )
    print(f"LLM connection passed: provider={provider} status={result.status}")
    print(result.message)


if __name__ == "__main__":
    main()
