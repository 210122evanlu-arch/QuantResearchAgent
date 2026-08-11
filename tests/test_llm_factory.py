from llm.deepseek_provider import DeepSeekStructuredLLM
from llm.factory import get_default_llm
from llm.gemini_provider import GeminiStructuredLLM
from llm.openai_provider import OpenAIStructuredLLM


def test_default_llm_factory_selects_gemini(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "offline-gemini-key")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    get_default_llm.cache_clear()

    provider = get_default_llm()

    assert isinstance(provider, GeminiStructuredLLM)
    get_default_llm.cache_clear()


def test_default_llm_factory_selects_deepseek(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "offline-deepseek-key")
    get_default_llm.cache_clear()

    provider = get_default_llm()

    assert isinstance(provider, DeepSeekStructuredLLM)
    get_default_llm.cache_clear()


def test_default_llm_factory_keeps_openai_fallback(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "offline-openai-key")
    get_default_llm.cache_clear()

    provider = get_default_llm()

    assert isinstance(provider, OpenAIStructuredLLM)
    get_default_llm.cache_clear()
