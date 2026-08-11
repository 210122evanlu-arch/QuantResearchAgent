"""Production LLM provider selection."""

from functools import lru_cache

from config import DeepSeekSettings, GeminiSettings, OpenAISettings, get_llm_provider
from llm.deepseek_provider import DeepSeekStructuredLLM
from llm.gemini_provider import GeminiStructuredLLM
from llm.openai_provider import OpenAIStructuredLLM
from llm.protocol import StructuredLLM


@lru_cache(maxsize=1)
def get_default_llm() -> StructuredLLM:
    """Lazily build the provider selected by ``LLM_PROVIDER``."""
    provider = get_llm_provider()
    if provider == "deepseek":
        return DeepSeekStructuredLLM(DeepSeekSettings.from_env())
    if provider == "gemini":
        return GeminiStructuredLLM(GeminiSettings.from_env())
    return OpenAIStructuredLLM(OpenAISettings.from_env())
