import logging

import pytest

from config import (
    BaoStockSettings,
    ConfigurationError,
    DeepSeekSettings,
    GeminiSettings,
    OpenAISettings,
    get_llm_provider,
    get_market_data_provider,
)
from logging_config import RedactingFormatter


def test_settings_require_api_key(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(ConfigurationError, match="OPENAI_API_KEY"):
        OpenAISettings.from_env(tmp_path / "missing.env")


def test_settings_load_safe_defaults(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv(
        "OPENAI_API_KEY", "sk-test-secret-value"
    )  # release-audit: allow-secret
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_REASONING_EFFORT", raising=False)
    monkeypatch.delenv("OPENAI_STORE", raising=False)

    settings = OpenAISettings.from_env(tmp_path / "missing.env")

    assert settings.model == "gpt-5.6-terra"
    assert settings.reasoning_effort == "medium"
    assert settings.store is False
    assert "sk-test-secret-value" not in repr(settings)  # release-audit: allow-secret


def test_log_formatter_redacts_api_key() -> None:
    formatter = RedactingFormatter("%(message)s")
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="credential=sk-abcdefghijklmnopqrstuvwxyz",  # release-audit: allow-secret
        args=(),
        exc_info=None,
    )

    rendered = formatter.format(record)

    assert (
        "sk-abcdefghijklmnopqrstuvwxyz" not in rendered
    )  # release-audit: allow-secret
    assert "[REDACTED_API_KEY]" in rendered


def test_gemini_settings_load_defaults(monkeypatch, tmp_path) -> None:
    gemini_key = "AIza" + "offline-test-key-12345678901234567890"
    monkeypatch.setenv("GEMINI_API_KEY", gemini_key)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)

    settings = GeminiSettings.from_env(tmp_path / "missing.env")

    assert settings.model == "gemini-3.6-flash"
    assert settings.temperature == 0.1
    assert gemini_key not in repr(settings)


def test_gemini_settings_require_api_key(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    with pytest.raises(ConfigurationError, match="GEMINI_API_KEY"):
        GeminiSettings.from_env(tmp_path / "missing.env")


def test_gemini_settings_prefer_google_api_key(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-fallback")
    monkeypatch.setenv("GOOGLE_API_KEY", "google-preferred")

    settings = GeminiSettings.from_env(tmp_path / "missing.env")

    assert settings.api_key == "google-preferred"


def test_llm_provider_defaults_to_deepseek(monkeypatch) -> None:
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    assert get_llm_provider() == "deepseek"


def test_llm_provider_rejects_unknown_value(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "unknown")
    with pytest.raises(ConfigurationError, match="LLM_PROVIDER"):
        get_llm_provider()


def test_log_formatter_redacts_gemini_api_key() -> None:
    formatter = RedactingFormatter("%(message)s")
    gemini_key = "AIza" + "offline123456789012345678901234567890"
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=f"credential={gemini_key}",
        args=(),
        exc_info=None,
    )

    rendered = formatter.format(record)

    assert gemini_key not in rendered
    assert "[REDACTED_API_KEY]" in rendered


def test_log_formatter_redacts_named_secret() -> None:
    formatter = RedactingFormatter("%(message)s")
    record = logging.LogRecord(
        name="test",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="provider failed DEEPSEEK_API_KEY=do-not-log-this",
        args=(),
        exc_info=None,
    )

    rendered = formatter.format(record)

    assert "do-not-log-this" not in rendered
    assert "DEEPSEEK_API_KEY=[REDACTED]" in rendered


def test_deepseek_settings_load_defaults(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "offline-deepseek-key")
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)

    settings = DeepSeekSettings.from_env(tmp_path / "missing.env")

    assert settings.model == "deepseek-v4-flash"
    assert settings.base_url == "https://api.deepseek.com"
    assert settings.thinking is False
    assert "offline-deepseek-key" not in repr(settings)


def test_deepseek_settings_require_api_key(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    with pytest.raises(ConfigurationError, match="DEEPSEEK_API_KEY"):
        DeepSeekSettings.from_env(tmp_path / "missing.env")


def test_market_data_provider_defaults_to_baostock(monkeypatch) -> None:
    monkeypatch.delenv("MARKET_DATA_PROVIDER", raising=False)
    assert get_market_data_provider() == "baostock"


def test_market_data_provider_rejects_unknown_value(monkeypatch) -> None:
    monkeypatch.setenv("MARKET_DATA_PROVIDER", "unknown")
    with pytest.raises(ConfigurationError, match="MARKET_DATA_PROVIDER"):
        get_market_data_provider()


def test_baostock_settings_reject_invalid_adjustment(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("BAOSTOCK_ADJUST_FLAG", "9")
    with pytest.raises(ConfigurationError, match="BAOSTOCK_ADJUST_FLAG"):
        BaoStockSettings.from_env(tmp_path / "missing.env")
