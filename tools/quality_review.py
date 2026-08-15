"""Independent deterministic checks before an advisory deliverable is released."""

from __future__ import annotations

from schemas.enums import (
    IssueSeverity,
    QualityReviewCategory,
    QualityReviewDecision,
    QualityReviewTarget,
)
from schemas.financial_risk import (
    AuditTrail,
    FinancialRiskInput,
    FinancialRiskScorecard,
)
from schemas.platform import EvidenceRecord
from schemas.quality_review import QualityCheck, QualityFinding, QualityReviewResult
from tools.financial_risk import payload_hash, screen_financial_anomalies

REQUIRED_REPORT_HEADINGS = (
    "## 执行摘要",
    "## 财务异常风险信号",
    "## 管理行动路线",
    "## 事实、推断与建议边界",
    "## 证据附录",
)
FORBIDDEN_ASSURANCE_CLAIMS = (
    "确认财务造假",
    "确定存在财务造假",
    "已经构成财务舞弊",
    "审计保证",
)


def _check(
    check_id: str,
    category: QualityReviewCategory,
    description: str,
    passed: bool,
    details: str,
    *,
    blocking: bool = False,
) -> QualityCheck:
    return QualityCheck(
        check_id=check_id,
        category=category,
        description=description,
        passed=passed,
        blocking=blocking and not passed,
        details=details,
    )


def run_quality_review(
    data: FinancialRiskInput,
    scorecard: FinancialRiskScorecard,
    evidence: list[EvidenceRecord],
    draft_report: str,
    audit_trail: AuditTrail,
) -> QualityReviewResult:
    """Recalculate outputs and test evidence, cutoff, report, and audit metadata."""
    known_evidence = {item.evidence_id for item in evidence}
    referenced = {
        evidence_id
        for signal in scorecard.signals
        for evidence_id in signal.evidence_ids
    }
    published_in_time = all(
        item.published_at is None or item.published_at.date() <= data.as_of_date
        for item in evidence
    )
    unique_evidence = len(known_evidence) == len(evidence)
    evidence_complete = bool(referenced) and referenced.issubset(known_evidence)
    reproduced = screen_financial_anomalies(data)
    reproducible = reproduced == scorecard
    hashes_match = (
        audit_trail.input_hash == payload_hash(data)
        and audit_trail.output_hash == payload_hash(scorecard)
        and audit_trail.methodology_version == scorecard.methodology_version
    )
    headings_complete = all(
        heading in draft_report for heading in REQUIRED_REPORT_HEADINGS
    )
    report_consistent = (
        f"{scorecard.risk_score:.1f}" in draft_report
        and scorecard.risk_level.value in draft_report
        and all(code in draft_report for code in scorecard.reason_codes)
    )
    actions_complete = all(
        signal.action.owner
        and signal.action.timeline
        and signal.action.actions
        and signal.action.kpis
        for signal in scorecard.signals
        if signal.triggered
    )
    assurance_safe = not any(
        phrase in draft_report for phrase in FORBIDDEN_ASSURANCE_CLAIMS
    )
    checks = [
        _check(
            "IQR-EVIDENCE-CUTOFF",
            QualityReviewCategory.EVIDENCE,
            "All evidence was public by the engagement cutoff date.",
            published_in_time,
            "No post-cutoff evidence detected."
            if published_in_time
            else "At least one evidence record is dated after the cutoff.",
            blocking=True,
        ),
        _check(
            "IQR-EVIDENCE-LINEAGE",
            QualityReviewCategory.EVIDENCE,
            "Signal evidence IDs are unique and resolve to the evidence register.",
            unique_evidence and evidence_complete,
            f"Resolved {len(referenced.intersection(known_evidence))}/{len(referenced)} referenced IDs.",
            blocking=True,
        ),
        _check(
            "IQR-MODEL-REPRODUCE",
            QualityReviewCategory.MODEL,
            "The scorecard reproduces from the same structured input.",
            reproducible,
            "Independent deterministic recalculation matched."
            if reproducible
            else "Independent recalculation produced a different scorecard.",
            blocking=True,
        ),
        _check(
            "IQR-AUDIT-TRAIL",
            QualityReviewCategory.AI_GOVERNANCE,
            "Input/output hashes and methodology version match the audit trail.",
            hashes_match,
            f"Run ID: {audit_trail.run_id}.",
            blocking=True,
        ),
        _check(
            "IQR-REPORT-CONTRACT",
            QualityReviewCategory.REPORT,
            "Required report sections are present.",
            headings_complete,
            "Required headings complete."
            if headings_complete
            else "One or more required headings are absent.",
        ),
        _check(
            "IQR-REPORT-CONSISTENCY",
            QualityReviewCategory.REPORT,
            "Risk score, level, and reason codes agree with the scorecard.",
            report_consistent,
            "Report values match structured output."
            if report_consistent
            else "Report and scorecard differ.",
            blocking=True,
        ),
        _check(
            "IQR-ACTION-COMPLETE",
            QualityReviewCategory.REPORT,
            "Each triggered signal has an owner, timeline, actions, and KPIs.",
            actions_complete,
            "All triggered signals have accountable actions."
            if actions_complete
            else "At least one triggered signal lacks an action field.",
        ),
        _check(
            "IQR-ASSURANCE-BOUNDARY",
            QualityReviewCategory.REPORT,
            "The report avoids unsupported fraud or audit-assurance conclusions.",
            assurance_safe,
            "No prohibited assurance language detected."
            if assurance_safe
            else "Unsupported assurance language was detected.",
            blocking=True,
        ),
    ]
    target_by_check = {
        "IQR-EVIDENCE-CUTOFF": QualityReviewTarget.EVIDENCE_COLLECTION,
        "IQR-EVIDENCE-LINEAGE": QualityReviewTarget.EVIDENCE_COLLECTION,
        "IQR-MODEL-REPRODUCE": QualityReviewTarget.FINANCIAL_RISK_ANALYSIS,
        "IQR-AUDIT-TRAIL": QualityReviewTarget.FINANCIAL_RISK_ANALYSIS,
        "IQR-REPORT-CONTRACT": QualityReviewTarget.DRAFT_REPORT,
        "IQR-REPORT-CONSISTENCY": QualityReviewTarget.DRAFT_REPORT,
        "IQR-ACTION-COMPLETE": QualityReviewTarget.FINANCIAL_RISK_ANALYSIS,
        "IQR-ASSURANCE-BOUNDARY": QualityReviewTarget.DRAFT_REPORT,
    }
    findings = [
        QualityFinding(
            finding_id=f"F-{check.check_id}",
            category=check.category,
            severity=(IssueSeverity.CRITICAL if check.blocking else IssueSeverity.HIGH),
            description=check.details,
            remediation="Resolve the failed control and rerun quality review.",
            target=target_by_check[check.check_id],
            blocking=check.blocking,
        )
        for check in checks
        if not check.passed
    ]
    coverage = (
        len(referenced.intersection(known_evidence)) / len(referenced)
        if referenced
        else 0.0
    )
    blocking = [finding for finding in findings if finding.blocking]
    if blocking:
        decision = QualityReviewDecision.BLOCKED
        revision_target = None
        assessment = "Delivery is blocked by a critical quality-control failure."
    elif findings:
        decision = QualityReviewDecision.REMEDIATION_REQUIRED
        revision_target = findings[0].target
        assessment = "Remediation is required before human sign-off."
    else:
        decision = QualityReviewDecision.PASSED
        revision_target = None
        assessment = "Automated engagement-quality controls passed; human sign-off remains required."
    return QualityReviewResult(
        decision=decision,
        checks=checks,
        findings=findings,
        revision_target=revision_target,
        evidence_coverage=coverage,
        reproducible=reproducible and hashes_match,
        report_consistent=report_consistent and headings_complete,
        overall_assessment=assessment,
    )
