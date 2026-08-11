"""OpenAI implementation of the structured LLM interface."""

import logging

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from config import OpenAISettings
from llm.errors import StructuredOutputError
from llm.protocol import SchemaT

logger = logging.getLogger(__name__)


class OpenAIStructuredLLM:
    """Generate strict Pydantic outputs through OpenAI's Responses API."""

    def __init__(self, settings: OpenAISettings) -> None:
        self.settings = settings
        self._model = ChatOpenAI(
            model=settings.model,
            api_key=SecretStr(settings.api_key),
            reasoning_effort=settings.reasoning_effort,
            timeout=settings.timeout_seconds,
            max_retries=settings.max_retries,
            store=settings.store,
            use_responses_api=True,
        )

    def generate(
        self,
        *,
        schema: type[SchemaT],
        system_prompt: str,
        user_prompt: str,
        node_name: str,
    ) -> SchemaT:
        logger.info(
            "Generating structured output node=%s schema=%s model=%s",
            node_name,
            schema.__name__,
            self.settings.model,
        )

        runnable = self._model.with_structured_output(
            schema,
            method="json_schema",
            strict=True,
        )
        try:
            result = runnable.invoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_prompt),
                ]
            )
        except Exception as exc:
            logger.error(
                "Structured output failed node=%s error_type=%s",
                node_name,
                type(exc).__name__,
            )
            raise StructuredOutputError(
                f"Structured output failed for node {node_name!r}"
            ) from exc

        if isinstance(result, schema):
            return result

        try:
            return schema.model_validate(result)
        except Exception as exc:
            raise StructuredOutputError(
                f"Provider returned invalid {schema.__name__} for node {node_name!r}"
            ) from exc
