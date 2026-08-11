from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from examples.byd_event_study_demo import (
    _design,
    _evidence,
    _returns_fixture,
    run_byd_event_study_demo,
)
from graph.event_study import (
    EventStudyHandler,
    build_event_study_workflow,
    event_study_intake_node,
)
from graph.platform import WorkflowRegistry
from schemas.enums import ReviewDecision, TaskType
from schemas.event_study import EventStudyDesign
from schemas.platform import ResearchRequest
from tools.event_study import run_event_study


def _request() -> ResearchRequest:
    return ResearchRequest(
        task_type=TaskType.EVENT_STUDY,
        question="Test an announcement event.",
        companies=["BYD Company Limited"],
        securities=["002594.SZ"],
        as_of_date=date(2026, 8, 8),
    )


def _context(*, contaminated: bool = False) -> dict:
    return {
        "event_study_design": _design(),
        "returns": _returns_fixture(),
        "evidence": _evidence(),
        "return_data_provenance": "deterministic offline fixture",
        "contaminated": contaminated,
    }


def test_event_study_calculates_negative_significant_car() -> None:
    result = run_event_study(_returns_fixture(), _design())

    assert result.estimation_observations == 100
    assert result.beta == pytest.approx(1.08, abs=0.15)
    short = result.window_results[0]
    assert short.cumulative_abnormal_return < -0.03
    assert short.p_value is not None and short.p_value < 0.05
    assert short.significant is True


def test_event_study_rejects_duplicate_dates() -> None:
    frame = _returns_fixture()
    frame.loc[1, "date"] = frame.loc[0, "date"]
    with pytest.raises(ValueError, match="duplicate dates"):
        run_event_study(frame, _design())


def test_event_study_design_rejects_post_event_estimation() -> None:
    with pytest.raises(ValidationError, match="pre-event"):
        EventStudyDesign(
            company_name="Example",
            security_code="002594.SZ",
            event_title="Event",
            event_date=date(2026, 5, 6),
            benchmark_name="Market",
            estimation_window=(-20, 1),
        )


def test_byd_event_study_demo_runs_end_to_end(tmp_path: Path) -> None:
    output = tmp_path / "event_study.md"
    result = run_byd_event_study_demo(output)

    assert result["event_study_review"].decision == ReviewDecision.APPROVED
    assert result["current_stage"] == "event_report"
    content = output.read_text(encoding="utf-8")
    assert "## 方法与估计设计" in content
    assert "累计异常收益" in content
    assert "确定性离线方法夹具" in content
    assert "不得被解释为" in content
    assert "BYD-ES-E1" in content


def test_contaminated_event_reaches_qualified_report_after_limit(
    tmp_path: Path,
) -> None:
    workflow = build_event_study_workflow(report_path=tmp_path / "qualified.md")
    result = workflow.invoke(
        {
            "request": _request(),
            "analysis_context": _context(contaminated=True),
            "revision_count": 0,
            "max_revisions": 1,
        }
    )

    assert result["event_study_review"].decision == ReviewDecision.NEED_REVISION
    assert result["revision_limit_reached"] is True
    assert result["current_stage"] == "event_report"


def test_event_study_intake_rejects_other_service_line() -> None:
    request = ResearchRequest(
        task_type=TaskType.QUANT_RESEARCH,
        question="Run a factor study.",
        as_of_date=date(2026, 8, 8),
    )
    with pytest.raises(ValueError, match="task_type=event_study"):
        event_study_intake_node({"request": request})


def test_event_study_handler_registers_on_platform(tmp_path: Path) -> None:
    platform = WorkflowRegistry()
    platform.register(
        TaskType.EVENT_STUDY,
        EventStudyHandler(
            build_event_study_workflow(report_path=tmp_path / "registered.md"),
            context_provider=lambda _request: _context(),
        ),
    )
    routed = platform.dispatch(_request())

    assert routed["workflow_selection"].workflow_name == "event_study"
    assert (
        routed["workflow_result"]["event_study_review"].decision
        == ReviewDecision.APPROVED
    )
