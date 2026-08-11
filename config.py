"""Environment-backed application settings."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


class ConfigurationError(RuntimeError):
    """Raised when required application configuration is missing or invalid."""


_REASONING_EFFORTS = {"none", "low", "medium", "high", "xhigh", "max"}
_LLM_PROVIDERS = {"deepseek", "gemini", "openai"}


def get_llm_provider() -> str:
    """Return the selected production LLM provider name."""
    provider = os.getenv("LLM_PROVIDER", "deepseek").strip().lower()
    if provider not in _LLM_PROVIDERS:
        allowed = ", ".join(sorted(_LLM_PROVIDERS))
        raise ConfigurationError(f"LLM_PROVIDER must be one of: {allowed}")
    return provider


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigurationError(f"Invalid boolean value: {value!r}")


@dataclass(frozen=True)
class OpenAISettings:
    """Validated settings for the OpenAI model provider."""

    api_key: str = field(repr=False)
    model: str = "gpt-5.6-terra"
    reasoning_effort: str = "medium"
    timeout_seconds: float = 60.0
    max_retries: int = 2
    store: bool = False

    @classmethod
    def from_env(cls, env_file: str | Path | None = None) -> "OpenAISettings":
        """Load settings from an optional dotenv file and process environment."""
        load_dotenv(dotenv_path=env_file, override=False)

        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise ConfigurationError(
                "OPENAI_API_KEY is not configured. Copy .env.example to .env "
                "and add a valid key before running production nodes."
            )

        model = os.getenv("OPENAI_MODEL", "gpt-5.6-terra").strip()
        if not model:
            raise ConfigurationError("OPENAI_MODEL cannot be empty")

        reasoning_effort = (
            os.getenv("OPENAI_REASONING_EFFORT", "medium").strip().lower()
        )
        if reasoning_effort not in _REASONING_EFFORTS:
            allowed = ", ".join(sorted(_REASONING_EFFORTS))
            raise ConfigurationError(
                f"OPENAI_REASONING_EFFORT must be one of: {allowed}"
            )

        try:
            timeout_seconds = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "60"))
            max_retries = int(os.getenv("OPENAI_MAX_RETRIES", "2"))
        except ValueError as exc:
            raise ConfigurationError(
                "OPENAI_TIMEOUT_SECONDS and OPENAI_MAX_RETRIES must be numeric"
            ) from exc

        if timeout_seconds <= 0:
            raise ConfigurationError("OPENAI_TIMEOUT_SECONDS must be positive")
        if max_retries < 0:
            raise ConfigurationError("OPENAI_MAX_RETRIES must be non-negative")

        store = _parse_bool(os.getenv("OPENAI_STORE", "false"))

        return cls(
            api_key=api_key,
            model=model,
            reasoning_effort=reasoning_effort,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            store=store,
        )


@dataclass(frozen=True)
class GeminiSettings:
    """Validated settings for the Google Gemini model provider."""

    api_key: str = field(repr=False)
    model: str = "gemini-3.6-flash"
    temperature: float = 0.1
    timeout_seconds: float = 60.0
    max_retries: int = 2
    max_output_tokens: int = 8192

    @classmethod
    def from_env(cls, env_file: str | Path | None = None) -> "GeminiSettings":
        """Load Gemini settings from dotenv and process environment."""
        load_dotenv(dotenv_path=env_file, override=False)

        # Match the official SDK's precedence when both variables are present.
        api_key = (
            os.getenv("GOOGLE_API_KEY", "").strip()
            or os.getenv("GEMINI_API_KEY", "").strip()
        )
        if not api_key:
            raise ConfigurationError(
                "GEMINI_API_KEY is not configured. Copy .env.example to .env "
                "and add a valid Google AI Studio key."
            )

        model = os.getenv("GEMINI_MODEL", "gemini-3.6-flash").strip()
        if not model:
            raise ConfigurationError("GEMINI_MODEL cannot be empty")

        try:
            temperature = float(os.getenv("GEMINI_TEMPERATURE", "0.1"))
            timeout_seconds = float(os.getenv("GEMINI_TIMEOUT_SECONDS", "60"))
            max_retries = int(os.getenv("GEMINI_MAX_RETRIES", "2"))
            max_output_tokens = int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", "8192"))
        except ValueError as exc:
            raise ConfigurationError(
                "Gemini numeric settings contain an invalid value"
            ) from exc

        if not 0 <= temperature <= 1:
            raise ConfigurationError("GEMINI_TEMPERATURE must be between 0 and 1")
        if timeout_seconds <= 0:
            raise ConfigurationError("GEMINI_TIMEOUT_SECONDS must be positive")
        if max_retries < 0:
            raise ConfigurationError("GEMINI_MAX_RETRIES must be non-negative")
        if max_output_tokens <= 0:
            raise ConfigurationError("GEMINI_MAX_OUTPUT_TOKENS must be positive")

        return cls(
            api_key=api_key,
            model=model,
            temperature=temperature,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            max_output_tokens=max_output_tokens,
        )


@dataclass(frozen=True)
class DeepSeekSettings:
    """Validated settings for the DeepSeek OpenAI-compatible API."""

    api_key: str = field(repr=False)
    model: str = "deepseek-v4-flash"
    base_url: str = "https://api.deepseek.com"
    temperature: float = 0.1
    timeout_seconds: float = 60.0
    max_retries: int = 2
    max_output_tokens: int = 8192
    thinking: bool = False

    @classmethod
    def from_env(cls, env_file: str | Path | None = None) -> "DeepSeekSettings":
        """Load DeepSeek settings from dotenv and process environment."""
        load_dotenv(dotenv_path=env_file, override=False)

        api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
        if not api_key:
            raise ConfigurationError(
                "DEEPSEEK_API_KEY is not configured. Add a valid DeepSeek key "
                "to the local .env file."
            )

        model = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash").strip()
        base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip()
        if not model:
            raise ConfigurationError("DEEPSEEK_MODEL cannot be empty")
        if not base_url.startswith("https://"):
            raise ConfigurationError("DEEPSEEK_BASE_URL must use HTTPS")

        try:
            temperature = float(os.getenv("DEEPSEEK_TEMPERATURE", "0.1"))
            timeout_seconds = float(os.getenv("DEEPSEEK_TIMEOUT_SECONDS", "60"))
            max_retries = int(os.getenv("DEEPSEEK_MAX_RETRIES", "2"))
            max_output_tokens = int(os.getenv("DEEPSEEK_MAX_OUTPUT_TOKENS", "8192"))
        except ValueError as exc:
            raise ConfigurationError(
                "DeepSeek numeric settings contain an invalid value"
            ) from exc

        if not 0 <= temperature <= 1:
            raise ConfigurationError("DEEPSEEK_TEMPERATURE must be between 0 and 1")
        if timeout_seconds <= 0:
            raise ConfigurationError("DEEPSEEK_TIMEOUT_SECONDS must be positive")
        if max_retries < 0:
            raise ConfigurationError("DEEPSEEK_MAX_RETRIES must be non-negative")
        if max_output_tokens <= 0:
            raise ConfigurationError("DEEPSEEK_MAX_OUTPUT_TOKENS must be positive")

        return cls(
            api_key=api_key,
            model=model,
            base_url=base_url.rstrip("/"),
            temperature=temperature,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            max_output_tokens=max_output_tokens,
            thinking=_parse_bool(os.getenv("DEEPSEEK_THINKING", "false")),
        )


@dataclass(frozen=True)
class TushareSettings:
    """Validated local settings for Tushare Pro market-data access."""

    token: str = field(repr=False)
    cache_directory: Path = Path("data/tushare")

    @classmethod
    def from_env(cls, env_file: str | Path | None = None) -> "TushareSettings":
        load_dotenv(dotenv_path=env_file, override=False)
        token = os.getenv("TUSHARE_TOKEN", "").strip()
        if not token:
            raise ConfigurationError(
                "TUSHARE_TOKEN is not configured. Register at tushare.pro and add "
                "the token to the local .env file."
            )
        cache_directory = Path(
            os.getenv("TUSHARE_CACHE_DIR", "data/tushare").strip() or "data/tushare"
        )
        return cls(token=token, cache_directory=cache_directory)


@dataclass(frozen=True)
class BaoStockSettings:
    """Local settings for the free BaoStock market-data adapter."""

    cache_directory: Path = Path("data/baostock")
    adjust_flag: str = "2"

    @classmethod
    def from_env(cls, env_file: str | Path | None = None) -> "BaoStockSettings":
        load_dotenv(dotenv_path=env_file, override=False)
        cache_directory = Path(
            os.getenv("BAOSTOCK_CACHE_DIR", "data/baostock").strip() or "data/baostock"
        )
        adjust_flag = os.getenv("BAOSTOCK_ADJUST_FLAG", "2").strip()
        if adjust_flag not in {"1", "2", "3"}:
            raise ConfigurationError(
                "BAOSTOCK_ADJUST_FLAG must be 1 (back-adjusted), "
                "2 (forward-adjusted), or 3 (unadjusted)"
            )
        return cls(cache_directory=cache_directory, adjust_flag=adjust_flag)


def get_market_data_provider() -> str:
    """Return the selected market-data provider; BaoStock is the free default."""
    provider = os.getenv("MARKET_DATA_PROVIDER", "baostock").strip().lower()
    if provider not in {"baostock", "tushare"}:
        raise ConfigurationError(
            "MARKET_DATA_PROVIDER must be one of: baostock, tushare"
        )
    return provider
