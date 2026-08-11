"""DeepSeek implementation of the structured LLM interface."""

import json
import logging

from openai import OpenAI

from config import DeepSeekSettings
from llm.errors import StructuredOutputError
from llm.protocol import SchemaT

logger = logging.getLogger(__name__)


class DeepSeekStructuredLLM:
    """Generate JSON through DeepSeek and validate it with Pydantic."""

    def __init__(self, settings: DeepSeekSettings) -> None:
        self.settings = settings
        self._client = OpenAI(
            api_key=settings.api_key,
            base_url=settings.base_url,
            timeout=settings.timeout_seconds,
            max_retries=settings.max_retries,
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
            "Generating structured output node=%s schema=%s model=%s provider=deepseek",
            node_name,
            schema.__name__,
            self.settings.model,
        )
        schema_json = json.dumps(schema.model_json_schema(), ensure_ascii=False)
        structured_system_prompt = (
            f"{system_prompt}\n\n"
            "Return one valid JSON object only. The JSON must conform exactly to "
            f"this JSON Schema: {schema_json}"
        )
        try:
            completion = self._client.chat.completions.create(
                model=self.settings.model,
                messages=[
                    {"role": "system", "content": structured_system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=self.settings.temperature,
                max_tokens=self.settings.max_output_tokens,
                extra_body={
                    "thinking": {
                        "type": "enabled" if self.settings.thinking else "disabled"
                    }
                },
            )
        except Exception as exc:
            logger.error(
                "Structured output failed node=%s provider=deepseek error_type=%s",
                node_name,
                type(exc).__name__,
            )
            raise StructuredOutputError(
                f"DeepSeek structured output failed for node {node_name!r}"
            ) from exc

        content = completion.choices[0].message.content
        if not content:
            raise StructuredOutputError(
                f"DeepSeek returned empty content for node {node_name!r}"
            )
        try:
            return schema.model_validate_json(content)
        except Exception as exc:
            raise StructuredOutputError(
                f"DeepSeek returned invalid {schema.__name__} for node {node_name!r}"
            ) from exc
