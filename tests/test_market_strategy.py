from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from analysis_engines.router import AnalysisEngineRegistry
from examples.a_share_market_strategy_demo import (
    _context,
    _engine,
    run_a_share_market_strategy_demo,
)
from graph.market_strategy import (
    MarketStrategyHandler,
    build_market_strategy_workflow,
    market_strategy_intake_node,
)
from graph.platform import WorkflowRegistry
from schemas.enums import AnalysisMethod, ReviewDecision, TaskType
from schemas.market_strategy import (
    MarketRegime,
    MarketSignalSnapshot,
    MarketStrategyReport,
)
from schemas.platform import ResearchRequest
from tools.market_strategy import assess_market_regime


def _registry() -> AnalysisEngineRegistry:
    registry = AnalysisEngineRegistry()
    for method in (
        AnalysisMethod.MARKET_REGIME_ANALYSIS,
        AnalysisMethod.SCENARIO_ANALYSIS,
    ):
        registry.register(method, _engine(method))
    return registry


def _request() -> ResearchRequest:
    return ResearchRequest(
        task_type=TaskType.MARKET_STRATEGY,
        question="Assess the A-share market regime.",
        as_of_date=date(2025, 2, 28),
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0.8, MarketRegime.RISK_ON),
        (-0.8, MarketRegime.DEFENSIVE),
        (0.0, MarketRegime.BALANCED),
        (0.25, MarketRegime.TRANSITION),
    ],
)
def test_market_regime_score_thresholds(value: float, expected: MarketRegime) -> None:
    snapshot = MarketSignalSnapshot(
        growth_momentum=value,
        liquidity_support=value,
        valuation_attractiveness=value,
        earnings_momentum=value,
        risk_appetite=value,
        provenance="test fixture",
    )
    assert assess_market_regime(snapshot).regime == expected


def test_market_strategy_demo_runs_end_to_end(tmp_path: Path) -> None:
    output = tmp_path / "market.md"
    result = run_a_share_market_strategy_demo(output)

    assert result["market_strategy_review"].decision == ReviewDecision.APPROVED
    assert result["market_strategy_report"].regime == MarketRegime.TRANSITION
    assert result["current_stage"] == "market_report"
    content = output.read_text(encoding="utf-8")
    assert "## Partner View" in content
    assert "## 风格与行业配置矩阵" in content
    assert "## 三情景策略矩阵" in content
    assert "离线信号评分不代表实时市场状态" in content
    assert "MS-E1" in content


def test_market_scenario_probabilities_must_sum_to_one() -> None:
    result = run_a_share_market_strategy_demo()
    values = result["market_strategy_report"].model_dump()
    values["scenarios"][0]["probability"] = 0.40
    with pytest.raises(ValidationError, match="sum to one"):
        MarketStrategyReport.model_validate(values)


def test_market_strategy_intake_rejects_other_service_line() -> None:
    with pytest.raises(ValueError, match="task_type=market_strategy"):
        market_strategy_intake_node(
            {
                "request": ResearchRequest(
                    task_type=TaskType.QUANT_RESEARCH,
                    question="Run a factor study.",
                    as_of_date=date(2025, 2, 28),
                )
            }
        )


def test_market_strategy_handler_registers_on_platform(tmp_path: Path) -> None:
    platform = WorkflowRegistry()
    platform.register(
        TaskType.MARKET_STRATEGY,
        MarketStrategyHandler(
            build_market_strategy_workflow(
                _registry(), report_path=tmp_path / "registered.md"
            ),
            context_provider=lambda _request: _context(),
        ),
    )
    routed = platform.dispatch(_request())

    assert routed["workflow_selection"].workflow_name == "market_strategy"
    result = routed["workflow_result"]
    assert result["market_strategy_review"].decision == ReviewDecision.APPROVED
