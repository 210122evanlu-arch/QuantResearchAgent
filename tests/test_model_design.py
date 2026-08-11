import pytest
from pydantic import ValidationError

from agents.base import NodeInputError
from agents.model_design import ModelDesignValidationError, create_model_design_node
from llm.fake import FakeStructuredLLM
from schemas.model_design import ModelDesign
from schemas.research_analysis import ResearchAnalysis


def _analysis() -> ResearchAnalysis:
    return ResearchAnalysis.model_validate(
        {
            "related_theories": ["Asset pricing"],
            "existing_models": ["Cross-sectional regression"],
            "key_papers": [
                {
                    "title": "Verified fixture",
                    "authors": ["Author"],
                    "year": 2020,
                    "source": "Journal",
                    "key_finding": "Fixture finding",
                    "relevance": "Fixture relevance",
                }
            ],
            "theoretical_mechanism": "Risk or mispricing.",
            "research_gap": "Further tests needed.",
            "refined_hypotheses": [
                {
                    "hypothesis_id": "H1",
                    "statement": "IVOL predicts returns",
                    "dependent_variable": "future_return",
                    "independent_variable": "IVOL",
                    "expected_direction": "negative",
                    "rationale": "Asset-pricing test",
                }
            ],
        }
    )


def _design(*, formula: str = "future_return ~ IVOL + size") -> dict:
    return {
        "model_name": "Fama-MacBeth",
        "formula": formula,
        "estimator": "fama_macbeth",
        "dependent_variable": {
            "name": "future_return",
            "role": "dependent",
            "definition": "Next-month return",
        },
        "independent_variables": [
            {
                "name": "IVOL",
                "role": "independent",
                "definition": "Idiosyncratic volatility",
            }
        ],
        "control_variables": [
            {
                "name": "size",
                "role": "control",
                "definition": "Log market capitalization",
            }
        ],
        "fixed_effects": [],
        "standard_error_method": "Newey-West",
        "assumptions": ["Correct specification"],
        "endogeneity_strategy": ["Lag predictors"],
        "limitations": ["Residual endogeneity"],
    }


def test_model_schema_rejects_wrong_variable_role() -> None:
    payload = _design()
    payload["control_variables"][0]["role"] = "independent"

    with pytest.raises(ValidationError, match="control_variables"):
        ModelDesign.model_validate(payload)


def test_model_node_rejects_formula_that_omits_variable() -> None:
    node = create_model_design_node(
        FakeStructuredLLM({ModelDesign: _design(formula="future_return ~ IVOL")})
    )

    with pytest.raises(ModelDesignValidationError, match="size"):
        node({"research_analysis": _analysis()})


def test_model_node_requires_research_analysis() -> None:
    node = create_model_design_node(FakeStructuredLLM({ModelDesign: _design()}))

    with pytest.raises(NodeInputError, match="research_analysis"):
        node({})


def test_model_node_rejects_hypothesis_dependent_variable_mismatch() -> None:
    payload = _design(formula="other_return ~ IVOL + size")
    payload["dependent_variable"]["name"] = "other_return"
    node = create_model_design_node(FakeStructuredLLM({ModelDesign: payload}))

    with pytest.raises(ModelDesignValidationError, match="future_return"):
        node({"research_analysis": _analysis()})


def test_model_node_rejects_hypothesis_independent_variable_mismatch() -> None:
    payload = _design(formula="future_return ~ beta + size")
    payload["independent_variables"][0]["name"] = "beta"
    node = create_model_design_node(FakeStructuredLLM({ModelDesign: payload}))

    with pytest.raises(ModelDesignValidationError, match="IVOL"):
        node({"research_analysis": _analysis()})
