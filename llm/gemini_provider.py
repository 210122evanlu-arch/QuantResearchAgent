"""Google Gemini implementation of the structured LLM interface."""

import logging

from google import genai
from google.genai import types

from config import GeminiSettings
from llm.errors import StructuredOutputError
from llm.protocol import SchemaT

logger = logging.getLogger(__name__)


class GeminiStructuredLLM:
    """Generate Pydantic outputs through the official Google Gen AI SDK."""

    def __init__(self, settings: GeminiSettings) -> None:
        self.settings = settings
        self._client = genai.Client(
            api_key=settings.api_key,
            http_options=types.HttpOptions(
                timeout=int(settings.timeout_seconds * 1000),
                retry_options=types.HttpRetryOptions(
                    attempts=settings.max_retries + 1,
                ),
            ),
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
            "Generating structured output node=%s schema=%s model=%s provider=gemini",
            node_name,
            schema.__name__,
            self.settings.model,
        )
        try:
            response = self._client.models.generate_content(
                model=self.settings.model,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=self.settings.temperature,
                    max_output_tokens=self.settings.max_output_tokens,
                    response_mime_type="application/json",
                    response_schema=schema,
                ),
            )
        except Exception as exc:
            logger.error(
                "Structured output failed node=%s provider=gemini error_type=%s",
                node_name,
                type(exc).__name__,
            )
            raise StructuredOutputError(
                f"Gemini structured output failed for node {node_name!r}"
            ) from exc

        if isinstance(response.parsed, schema):
            return response.parsed
        if response.parsed is not None:
            try:
                return schema.model_validate(response.parsed)
            except Exception as exc:
                raise StructuredOutputError(
                    f"Gemini returned invalid {schema.__name__} for node {node_name!r}"
                ) from exc
        if response.text:
            try:
                return schema.model_validate_json(response.text)
            except Exception as exc:
                raise StructuredOutputError(
                    f"Gemini returned invalid {schema.__name__} for node {node_name!r}"
                ) from exc
        raise StructuredOutputError(
            f"Gemini returned no structured content for node {node_name!r}"
        )
