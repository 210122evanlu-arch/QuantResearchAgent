from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from analysis_engines.router import AnalysisEngineRegistry
from examples.company_research_demo import _engine, _evidence, run_company_research_demo
from graph.company_research import (
    CompanyResearchHandler,
    build_company_research_workflow,
    company_intake_node,
)
from graph.platform import WorkflowRegistry
from schemas.company_research import (
    CompanyResearchReviewIssue,
    CompanyResearchReviewResult,
    CompanyResearchRevisionTarget,
)
from schemas.enums import AnalysisMethod, IssueSeverity, ReviewDecision, TaskType
from schemas.platform import ResearchRequest


def test_company_research_demo_runs_end_to_end(tmp_path: Path) -> None:
    output = tmp_path / "company_research.md"
    result = run_company_research_demo(output)

    assert result["company_research_review"].decision == ReviewDecision.APPROVED
    assert result["current_stage"] == "company_report"
    assert result["revision_count"] == 0
    assert Path(result["report_markdown_path"]) == output.resolve()
    content = output.read_text(encoding="utf-8")
    assert "## Financial Quality" in content
    assert "## Valuation and Peer Comparison" in content
    assert "BYD-CR-E1" in content


def test_company_research_review_contract_requires_matching_target() -> None:
    with pytest.raises(ValidationError, match="must match"):
        CompanyResearchReviewResult(
            decision=ReviewDecision.NEED_REVISION,
            issues=[
                CompanyResearchReviewIssue(
                    severity=IssueSeverity.HIGH,
                    description="Evidence is incomplete.",
                    recommendation="Refresh the evidence set.",
                    target=CompanyResearchRevisionTarget.ANALYSIS,
                )
            ],
            revision_target=CompanyResearchRevisionTarget.SYNTHESIS,
            overall_assessment="Revision required.",
        )


def test_company_intake_rejects_a_different_service_line() -> None:
    request = ResearchRequest(
        task_type=TaskType.QUANT_RESEARCH,
        question="Run a factor study.",
        as_of_date=date(2026, 8, 8),
    )
    with pytest.raises(ValueError, match="task_type=company_research"):
        company_intake_node({"request": request})


def test_company_research_handler_registers_on_platform(tmp_path: Path) -> None:
    engines = AnalysisEngineRegistry()
    for method in (
        AnalysisMethod.FINANCIAL_STATEMENT_ANALYSIS,
        AnalysisMethod.STRATEGIC_DIAGNOSIS,
        AnalysisMethod.RELATIVE_VALUATION,
        AnalysisMethod.PEER_BENCHMARKING,
    ):
        engines.register(method, _engine(method))
    workflow = build_company_research_workflow(
        engines, report_path=tmp_path / "registered.md"
    )
    platform = WorkflowRegistry()
    platform.register(
        TaskType.COMPANY_RESEARCH,
        CompanyResearchHandler(
            workflow,
            context_provider=lambda _request: {"evidence": _evidence()},
        ),
    )
    routed = platform.dispatch(
        ResearchRequest(
            task_type=TaskType.COMPANY_RESEARCH,
            question="Research BYD.",
            companies=["BYD Company Limited"],
            securities=["002594.SZ"],
            as_of_date=date(2026, 8, 8),
            debate_requested=False,
        )
    )

    assert routed["workflow_selection"].workflow_name == "company_research"
    result = routed["workflow_result"]
    assert result["company_research_review"].decision == ReviewDecision.APPROVED
