import pytest
from pydantic import ValidationError

from analysis_engines.company import dcf_valuation_engine
from schemas.enums import AnalysisMethod, EvidenceStatus
from schemas.valuation import DCFInput, DCFSensitivityConfig
from tools.valuation import run_dcf


def _input() -> DCFInput:
    return DCFInput.model_validate(
        {
            "currency": "CNY",
            "projections": [
                {"year": 1, "free_cash_flow": 100},
                {"year": 2, "free_cash_flow": 110},
                {"year": 3, "free_cash_flow": 121},
                {"year": 4, "free_cash_flow": 133.1},
                {"year": 5, "free_cash_flow": 146.41},
            ],
            "discount_rate": 0.10,
            "terminal_growth_rate": 0.03,
            "net_debt": 200,
            "shares_outstanding": 100,
        }
    )


def test_dcf_calculates_base_case_and_sensitivity_grid() -> None:
    result = run_dcf(_input(), DCFSensitivityConfig(steps_each_side=2))
    assert result.enterprise_value > result.present_value_forecast
    assert result.equity_value == pytest.approx(result.enterprise_value - 200)
    assert result.value_per_share == pytest.approx(result.equity_value / 100)
    assert len(result.sensitivity) == 25
    assert (
        min(item.value_per_share for item in result.sensitivity)
        < result.value_per_share
    )
    assert (
        max(item.value_per_share for item in result.sensitivity)
        > result.value_per_share
    )


def test_dcf_rejects_terminal_growth_at_or_above_discount_rate() -> None:
    values = _input().model_dump()
    values["terminal_growth_rate"] = values["discount_rate"]
    with pytest.raises(ValidationError, match="must exceed"):
        DCFInput.model_validate(values)


def test_dcf_engine_preserves_assumption_driven_status() -> None:
    artifact = dcf_valuation_engine({"dcf_input": _input()})
    assert artifact.method == AnalysisMethod.DCF_VALUATION
    assert artifact.findings[0].status == EvidenceStatus.INFERRED
    assert "value_per_share" in artifact.metrics

    missing = dcf_valuation_engine({})
    assert missing.findings[0].status == EvidenceStatus.INSUFFICIENT
