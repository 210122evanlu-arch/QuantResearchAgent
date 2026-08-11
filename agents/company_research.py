"""Deterministic synthesis and quality review for company research."""

from dataclasses import dataclass

from schemas.company_research import (
    CompanyResearchReport,
    CompanyResearchReviewIssue,
    CompanyResearchReviewResult,
    CompanyResearchRevisionTarget,
)
from schemas.enums import (
    AnalysisMethod,
    EvidenceStatus,
    IssueSeverity,
    ReviewDecision,
    TaskType,
)
from schemas.platform import AnalysisArtifact, AnalysisBundle
from schemas.state import ResearchState


def _artifact(bundle: AnalysisBundle, method: AnalysisMethod) -> AnalysisArtifact:
    matches = [item for item in bundle.artifacts if item.method == method]
    if len(matches) != 1:
        raise ValueError(
            f"company research requires exactly one {method.value} artifact"
        )
    return matches[0]


@dataclass(frozen=True)
class CompanyResearchSynthesisNode:
    name: str = "company_synthesis"

    def __call__(self, state: ResearchState) -> dict:
        request = state["request"]
        bundle = state["analysis_bundle"]
        financial = _artifact(bundle, AnalysisMethod.FINANCIAL_STATEMENT_ANALYSIS)
        strategy = _artifact(bundle, AnalysisMethod.STRATEGIC_DIAGNOSIS)
        valuation = _artifact(bundle, AnalysisMethod.RELATIVE_VALUATION)
        peers = _artifact(bundle, AnalysisMethod.PEER_BENCHMARKING)

        company_name = (
            request.companies[0] if request.companies else request.securities[0]
        )
        security_code = request.securities[0] if request.securities else "NOT_PROVIDED"
        findings = [finding for item in bundle.artifacts for finding in item.findings]
        evidence_ids = list(
            dict.fromkeys(
                evidence_id
                for finding in findings
                for evidence_id in finding.evidence_ids
            )
        )
        implications = [finding.implication for finding in findings]
        metrics = [
            f"{item.method.value}: {key}={value}"
            for item in bundle.artifacts
            for key, value in item.metrics.items()
        ]
        key_metrics = {
            key: str(value)
            for item in bundle.artifacts
            for key, value in item.metrics.items()
        }
        limitations = list(
            dict.fromkeys(
                [
                    *bundle.warnings,
                    *(value for item in bundle.artifacts for value in item.limitations),
                ]
            )
        ) or ["Only the supplied public evidence was analysed."]
        report = CompanyResearchReport(
            title=f"{company_name}上市公司深度研究",
            company_name=company_name,
            security_code=security_code,
            as_of_date=request.as_of_date,
            executive_summary=" ".join(item.summary for item in bundle.artifacts),
            key_metrics=key_metrics,
            business_model=strategy.summary,
            competitive_position="; ".join(
                finding.statement for finding in strategy.findings
            ),
            financial_quality=financial.summary,
            peer_comparison=peers.summary,
            valuation=valuation.summary,
            catalysts=implications or ["No evidence-backed catalyst was identified."],
            risks=limitations,
            monitoring_indicators=metrics or ["Refresh the evidence set each quarter."],
            evidence_ids=evidence_ids,
            limitations=limitations,
            conclusion=(
                "The current evidence supports a conditional research view; update the "
                "conclusion when financial, peer, valuation, or material-event data change."
            ),
        )
        return {"company_research_report": report, "current_stage": self.name}


@dataclass(frozen=True)
class CompanyResearchReviewNode:
    minimum_evidence_records: int = 3
    name: str = "company_research_review"

    def __call__(self, state: ResearchState) -> dict:
        request = state["request"]
        selection = state["workflow_selection"]
        bundle = state["analysis_bundle"]
        report = state["company_research_report"]
        issues: list[CompanyResearchReviewIssue] = []
        produced = {item.method for item in bundle.artifacts}
        missing = set(selection.analysis_methods) - produced
        if missing:
            issues.append(
                CompanyResearchReviewIssue(
                    severity=IssueSeverity.HIGH,
                    description="Missing required analysis methods: "
                    + ", ".join(sorted(item.value for item in missing)),
                    recommendation="Run each router-selected analysis engine.",
                    target=CompanyResearchRevisionTarget.ANALYSIS,
                )
            )
        if len(bundle.evidence) < self.minimum_evidence_records:
            issues.append(
                CompanyResearchReviewIssue(
                    severity=IssueSeverity.HIGH,
                    description="The evidence set is too small for a deep-dive report.",
                    recommendation="Add current filings, market data, and peer evidence.",
                    target=CompanyResearchRevisionTarget.ANALYSIS,
                )
            )
        insufficient = [
            finding.finding_id
            for artifact in bundle.artifacts
            for finding in artifact.findings
            if finding.status == EvidenceStatus.INSUFFICIENT
        ]
        if insufficient:
            issues.append(
                CompanyResearchReviewIssue(
                    severity=IssueSeverity.HIGH,
                    description="Insufficient evidence for findings: "
                    + ", ".join(insufficient),
                    recommendation="Collect the missing filing, peer, or market evidence.",
                    target=CompanyResearchRevisionTarget.ANALYSIS,
                )
            )
        known = {item.evidence_id for item in bundle.evidence}
        if not set(report.evidence_ids).issubset(known):
            issues.append(
                CompanyResearchReviewIssue(
                    severity=IssueSeverity.CRITICAL,
                    description="The report contains an unknown evidence reference.",
                    recommendation="Remove or resolve unsupported evidence identifiers.",
                    target=CompanyResearchRevisionTarget.SYNTHESIS,
                )
            )
        if request.task_type != TaskType.COMPANY_RESEARCH:
            issues.append(
                CompanyResearchReviewIssue(
                    severity=IssueSeverity.CRITICAL,
                    description="The workflow received a non-company-research request.",
                    recommendation="Return the request to platform intake.",
                    target=CompanyResearchRevisionTarget.SYNTHESIS,
                )
            )

        if issues:
            target = issues[0].target
            result = CompanyResearchReviewResult(
                decision=ReviewDecision.NEED_REVISION,
                issues=issues,
                revision_target=target,
                overall_assessment="The report is not ready for delivery.",
            )
        else:
            result = CompanyResearchReviewResult(
                decision=ReviewDecision.APPROVED,
                strengths=[
                    "All router-selected methods were executed.",
                    "Report claims are traceable to the supplied evidence bundle.",
                    "Limitations and monitoring indicators are explicit.",
                ],
                overall_assessment="Approved as a public-information research deliverable.",
            )
        return {"company_research_review": result, "current_stage": self.name}
