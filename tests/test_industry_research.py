from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from analysis_engines.router import AnalysisEngineRegistry
from examples.baijiu_industry_research_demo import (
    _engine,
    _evidence,
    run_baijiu_industry_research_demo,
)
from graph.industry_research import (
    IndustryResearchHandler,
    build_industry_research_workflow,
    industry_intake_node,
)
from graph.platform import WorkflowRegistry
from schemas.enums import AnalysisMethod, IssueSeverity, ReviewDecision, TaskType
from schemas.industry_research import (
    IndustryResearchReviewIssue,
    IndustryResearchReviewResult,
    IndustryResearchRevisionTarget,
)
from schemas.platform import ResearchRequest

SCENARIOS = [
    {
        "name": "Base",
        "trigger": "Demand stabilises",
        "implications": ["Leaders retain an advantage"],
        "monitoring_indicators": ["channel inventory"],
    },
    {
        "name": "Downside",
        "trigger": "Demand weakens",
        "implications": ["Cash conversion deteriorates"],
        "monitoring_indicators": ["operating cash flow"],
    },
]


def _registry() -> AnalysisEngineRegistry:
    registry = AnalysisEngineRegistry()
    for method in (
        AnalysisMethod.INDUSTRY_ANALYSIS,
        AnalysisMethod.PEER_BENCHMARKING,
        AnalysisMethod.SCENARIO_ANALYSIS,
    ):
        registry.register(method, _engine(method))
    return registry


def test_baijiu_industry_demo_runs_end_to_end(tmp_path: Path) -> None:
    output = tmp_path / "industry.md"
    result = run_baijiu_industry_research_demo(output)

    assert result["industry_research_review"].decision == ReviewDecision.APPROVED
    assert result["current_stage"] == "industry_report"
    assert result["revision_count"] == 0
    content = output.read_text(encoding="utf-8")
    assert '<div align="center">' in content
    assert "## 情景矩阵" in content
    assert "## 局限性与适用边界" in content
    assert "仅覆盖两家公司" in content
    assert "BJ-E1" in content


def test_industry_review_contract_requires_matching_target() -> None:
    with pytest.raises(ValidationError, match="must match"):
        IndustryResearchReviewResult(
            decision=ReviewDecision.NEED_REVISION,
            issues=[
                IndustryResearchReviewIssue(
                    severity=IssueSeverity.HIGH,
                    description="Evidence is incomplete.",
                    recommendation="Refresh the evidence set.",
                    target=IndustryResearchRevisionTarget.ANALYSIS,
                )
            ],
            revision_target=IndustryResearchRevisionTarget.SYNTHESIS,
            overall_assessment="Revision required.",
        )


def test_industry_intake_rejects_a_different_service_line() -> None:
    request = ResearchRequest(
        task_type=TaskType.QUANT_RESEARCH,
        question="Run a factor study.",
        as_of_date=date(2026, 8, 8),
    )
    with pytest.raises(ValueError, match="task_type=industry_research"):
        industry_intake_node({"request": request})


def test_industry_handler_registers_on_platform(tmp_path: Path) -> None:
    workflow = build_industry_research_workflow(
        _registry(), report_path=tmp_path / "registered.md"
    )
    platform = WorkflowRegistry()
    platform.register(
        TaskType.INDUSTRY_RESEARCH,
        IndustryResearchHandler(
            workflow,
            context_provider=lambda _request: {
                "evidence": _evidence(),
                "scenarios": SCENARIOS,
            },
        ),
    )
    routed = platform.dispatch(
        ResearchRequest(
            task_type=TaskType.INDUSTRY_RESEARCH,
            question="Research high-end baijiu.",
            industries=["High-end baijiu"],
            as_of_date=date(2026, 8, 8),
        )
    )

    assert routed["workflow_selection"].workflow_name == "industry_research"
    result = routed["workflow_result"]
    assert result["industry_research_review"].decision == ReviewDecision.APPROVED
