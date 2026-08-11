from types import SimpleNamespace

import pytest

from config import DeepSeekSettings, GeminiSettings, OpenAISettings
from llm.deepseek_provider import DeepSeekStructuredLLM
from llm.errors import StructuredOutputError
from llm.fake import FakeStructuredLLM
from llm.gemini_provider import GeminiStructuredLLM
from llm.openai_provider import OpenAIStructuredLLM
from schemas.enums import ExpectedDirection, ResearchType
from schemas.research_plan import ResearchPlan


def valid_plan_payload() -> dict:
    return {
        "research_question": "Does IVOL predict future returns?",
        "research_objective": "Test the IVOL-return relation.",
        "research_type": ResearchType.PANEL,
        "hypotheses": [
            {
                "hypothesis_id": "H1",
                "statement": "IVOL negatively predicts future returns",
                "dependent_variable": "future_return",
                "independent_variable": "IVOL",
                "expected_direction": ExpectedDirection.NEGATIVE,
                "rationale": "Test rationale",
            }
        ],
        "methodology": "Fama-MacBeth regression",
        "required_data": ["returns", "factor returns"],
        "evaluation_metrics": ["coefficient", "t-stat"],
    }


def test_fake_llm_returns_validated_schema_and_records_call() -> None:
    llm = FakeStructuredLLM({ResearchPlan: valid_plan_payload()})

    result = llm.generate(
        schema=ResearchPlan,
        system_prompt="system",
        user_prompt="user",
        node_name="research_manager",
    )

    assert isinstance(result, ResearchPlan)
    assert result.hypotheses[0].hypothesis_id == "H1"
    assert llm.calls[0].node_name == "research_manager"


def test_fake_llm_fails_when_fixture_is_missing() -> None:
    llm = FakeStructuredLLM({})

    with pytest.raises(StructuredOutputError, match="ResearchPlan"):
        llm.generate(
            schema=ResearchPlan,
            system_prompt="system",
            user_prompt="user",
            node_name="research_manager",
        )


def test_openai_provider_can_be_constructed_without_network_call() -> None:
    provider = OpenAIStructuredLLM(
        OpenAISettings(
            api_key="sk-offline-construction-test"
        )  # release-audit: allow-secret
    )

    assert provider.settings.model == "gpt-5.6-terra"
    assert provider._model.use_responses_api is True


def test_gemini_provider_can_be_constructed_without_network_call() -> None:
    provider = GeminiStructuredLLM(GeminiSettings(api_key="offline-test-key"))

    assert provider.settings.model == "gemini-3.6-flash"


def test_gemini_provider_returns_parsed_schema_without_network_call() -> None:
    provider = GeminiStructuredLLM(GeminiSettings(api_key="offline-test-key"))
    expected = ResearchPlan.model_validate(valid_plan_payload())

    class FakeModels:
        def generate_content(self, **kwargs):
            assert kwargs["model"] == "gemini-3.6-flash"
            return SimpleNamespace(parsed=expected, text=expected.model_dump_json())

    provider._client = SimpleNamespace(models=FakeModels())

    result = provider.generate(
        schema=ResearchPlan,
        system_prompt="system",
        user_prompt="user",
        node_name="research_manager",
    )

    assert result == expected


def test_deepseek_provider_returns_validated_json_without_network_call() -> None:
    provider = DeepSeekStructuredLLM(DeepSeekSettings(api_key="offline-deepseek-key"))
    expected = ResearchPlan.model_validate(valid_plan_payload())

    class FakeCompletions:
        def create(self, **kwargs):
            assert kwargs["model"] == "deepseek-v4-flash"
            assert kwargs["response_format"] == {"type": "json_object"}
            message = SimpleNamespace(content=expected.model_dump_json())
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    provider._client = SimpleNamespace(
        chat=SimpleNamespace(completions=FakeCompletions())
    )

    result = provider.generate(
        schema=ResearchPlan,
        system_prompt="system",
        user_prompt="user",
        node_name="research_manager",
    )

    assert result == expected
