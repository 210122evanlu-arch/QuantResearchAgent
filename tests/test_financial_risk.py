from datetime import UTC, datetime

from examples.financial_anomaly_risk_demo import (
    AS_OF_DATE,
    _evidence,
    _input,
    run_financial_anomaly_risk_demo,
)
from graph.financial_risk import quality_decision_router, quality_revision_router
from schemas.enums import (
    FinancialRiskLevel,
    QualityReviewDecision,
    QualityReviewTarget,
    SignOffStatus,
)
from schemas.platform import EvidenceRecord
from tools.financial_risk import build_audit_trail, screen_financial_anomalies
from tools.financial_risk_report import render_financial_risk_report
from tools.quality_review import run_quality_review


def test_financial_screening_is_explainable_and_reproducible() -> None:
    data = _input()
    first = screen_financial_anomalies(data)
    second = screen_financial_anomalies(data)

    assert first == second
    assert first.risk_level == FinancialRiskLevel.CRITICAL
    assert first.risk_score == 71.1
    assert "FR-CASH-CONVERSION" in first.reason_codes
    assert "FR-AUDIT-OPINION" not in first.reason_codes
    assert all(signal.action.owner for signal in first.signals if signal.triggered)


def test_quality_review_recalculates_and_passes_complete_draft() -> None:
    data = _input()
    scorecard = screen_financial_anomalies(data)
    trail = build_audit_trail(data, scorecard, code_version="test")
    draft = render_financial_risk_report(
        data, scorecard, _evidence(), audit_trail=trail
    )

    result = run_quality_review(data, scorecard, _evidence(), draft, trail)

    assert result.decision == QualityReviewDecision.PASSED
    assert result.evidence_coverage == 1
    assert result.reproducible
    assert result.report_consistent
    assert quality_decision_router({"quality_review_result": result}) == "passed"


def test_quality_review_blocks_post_cutoff_evidence() -> None:
    data = _input()
    scorecard = screen_financial_anomalies(data)
    trail = build_audit_trail(data, scorecard, code_version="test")
    evidence = _evidence()
    evidence.append(
        EvidenceRecord(
            evidence_id="POST-CUTOFF",
            source_type="fixture",
            title="Post-cutoff record",
            source_name="Fixture",
            published_at=datetime(2026, 5, 1, tzinfo=UTC),
            retrieved_at=datetime(2026, 5, 2, tzinfo=UTC),
            summary="Must not be used by the engagement.",
        )
    )
    draft = render_financial_risk_report(data, scorecard, evidence, audit_trail=trail)

    result = run_quality_review(data, scorecard, evidence, draft, trail)

    assert result.decision == QualityReviewDecision.BLOCKED
    assert any(item.blocking for item in result.findings)
    assert quality_decision_router({"quality_review_result": result}) == "blocked"


def test_quality_review_routes_report_contract_remediation() -> None:
    data = _input()
    scorecard = screen_financial_anomalies(data)
    trail = build_audit_trail(data, scorecard, code_version="test")
    draft = render_financial_risk_report(
        data, scorecard, _evidence(), audit_trail=trail
    ).replace("## 管理行动路线", "## Action Plan")

    result = run_quality_review(data, scorecard, _evidence(), draft, trail)

    assert result.decision == QualityReviewDecision.REMEDIATION_REQUIRED
    assert result.revision_target == QualityReviewTarget.DRAFT_REPORT
    state = {
        "quality_review_result": result,
        "revision_limit_reached": False,
    }
    assert quality_decision_router(state) == "remediation"
    assert quality_revision_router(state) == "draft"


def test_end_to_end_financial_risk_delivery_requires_human_signoff(tmp_path) -> None:
    report_path = tmp_path / "financial-risk.md"

    result = run_financial_anomaly_risk_demo(report_path)

    assert result["quality_review_result"].decision == QualityReviewDecision.PASSED
    assert result["human_signoff"].status == SignOffStatus.PENDING
    assert result["current_stage"] == "controlled_delivery"
    content = report_path.read_text(encoding="utf-8")
    assert "财务异常风险信号" in content
    assert "内部质量复核" in content
    assert "人工签署" in content
    assert "IQR passed / 人工签署待定" in content
    assert AS_OF_DATE.isoformat() in content
    assert "| FR-CASH-CONVERSION | earnings_quality | 利润现金转化 | 0.41x |" in content
    assert "| FR-AR-GAP | working_capital | 应收增速偏离收入 | 55.16% |" in content
