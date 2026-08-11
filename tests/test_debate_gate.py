from datetime import date

import pytest

from examples.byd_risk_advisory_demo import run_byd_risk_advisory_demo
from examples.debate_workflow_demo import _initial_state
from graph.debate_gate import (
    DebateGateConfig,
    build_gated_debate_workflow,
    evaluate_debate_gate,
)
from schemas.enums import (
    AnalysisMethod,
    DebateGateDecision,
    DebateTrigger,
    EvidenceStatus,
    TaskType,
)
from schemas.platform import (
    AnalysisArtifact,
    AnalysisBundle,
    ResearchFinding,
    ResearchRequest,
)


def _request(task_type=TaskType.QUANT_RESEARCH, **updates) -> ResearchRequest:
    values = {
        "task_type": task_type,
        "question": "Fixture request",
        "as_of_date": date(2026, 8, 7),
    }
    if task_type == TaskType.CORPORATE_ADVISORY:
        values["companies"] = ["Fixture Company"]
    values.update(updates)
    return ResearchRequest.model_validate(values)


def _analysis(confidence=0.9, status=EvidenceStatus.VERIFIED, warnings=None):
    finding = ResearchFinding(
        finding_id="F1",
        statement="Fixture finding",
        implication="Fixture implication",
        evidence_ids=["E1"] if status == EvidenceStatus.VERIFIED else [],
        status=status,
        confidence=confidence,
    )
    artifact = AnalysisArtifact(
        method=AnalysisMethod.REGRESSION,
        title="Fixture",
        summary="Fixture",
        findings=[finding],
    )
    if status == EvidenceStatus.VERIFIED:
        return _initial_state()["analysis_bundle"].model_copy(
            update={"artifacts": [artifact], "warnings": warnings or []}
        )
    return AnalysisBundle(artifacts=[artifact], warnings=warnings or [])


def test_gate_skips_well_supported_routine_quant_analysis() -> None:
    result = evaluate_debate_gate(_request(), _analysis())
    assert result.decision == DebateGateDecision.SKIP_DEBATE
    assert result.triggers == []


def test_gate_enters_for_material_advisory_and_user_request() -> None:
    result = evaluate_debate_gate(
        _request(TaskType.CORPORATE_ADVISORY, debate_requested=True),
        _analysis(),
    )
    assert result.decision == DebateGateDecision.ENTER_DEBATE
    assert result.triggers[:2] == [
        DebateTrigger.USER_REQUESTED,
        DebateTrigger.MATERIAL_ADVISORY,
    ]


def test_explicit_user_opt_out_skips_automatic_debate() -> None:
    result = evaluate_debate_gate(
        _request(TaskType.CORPORATE_ADVISORY, debate_requested=False),
        _analysis(confidence=0.2),
    )
    assert result.decision == DebateGateDecision.SKIP_DEBATE


def test_gated_pipeline_does_not_call_debate_on_skip_path() -> None:
    def analysis_node(state):
        return {"analysis_bundle": _analysis()}

    def forbidden_debate(state):
        raise AssertionError("debate should have been skipped")

    workflow = build_gated_debate_workflow(analysis_node, forbidden_debate)
    result = workflow.invoke({"request": _request()})
    assert result["debate_gate_result"].decision == DebateGateDecision.SKIP_DEBATE
    assert "debate_result" not in result


def test_low_confidence_and_warning_are_auditable_triggers() -> None:
    result = evaluate_debate_gate(
        _request(),
        _analysis(confidence=0.4, warnings=["Evidence conflict remains"]),
    )
    assert result.decision == DebateGateDecision.ENTER_DEBATE
    assert DebateTrigger.LOW_CONFIDENCE in result.triggers
    assert DebateTrigger.ANALYSIS_WARNING in result.triggers
    assert DebateTrigger.EVIDENCE_CONFLICT in result.triggers


@pytest.mark.parametrize(
    "options",
    [{"max_rounds": 0}, {"max_rounds": 6}, {"confidence_threshold": 1.1}],
)
def test_invalid_gate_policy_is_rejected(options) -> None:
    with pytest.raises(ValueError):
        DebateGateConfig(**options)


def test_byd_advisory_enters_debate_and_writes_evidence_report(tmp_path) -> None:
    report_path = tmp_path / "byd.md"
    result, llm = run_byd_risk_advisory_demo(report_path)
    content = report_path.read_text(encoding="utf-8")

    assert result["debate_gate_result"].decision == DebateGateDecision.ENTER_DEBATE
    assert len(result["debate_result"].rounds) == 2
    assert len(llm.calls) == 6
    assert "盈利质量与现金转化" in content
    assert "BYD-E6" in content
    assert "https://static.cninfo.com.cn" in content
