"""Deterministic synthesis and committee review for industry research."""

from dataclasses import dataclass

from schemas.enums import (
    AnalysisMethod,
    EvidenceStatus,
    IssueSeverity,
    ReviewDecision,
    TaskType,
)
from schemas.industry_research import (
    IndustryResearchReport,
    IndustryResearchReviewIssue,
    IndustryResearchReviewResult,
    IndustryResearchRevisionTarget,
    IndustryScenario,
)
from schemas.platform import AnalysisArtifact, AnalysisBundle
from schemas.state import ResearchState


def _artifact(bundle: AnalysisBundle, method: AnalysisMethod) -> AnalysisArtifact:
    matches = [item for item in bundle.artifacts if item.method == method]
    if len(matches) != 1:
        raise ValueError(
            f"industry research requires exactly one {method.value} artifact"
        )
    return matches[0]


@dataclass(frozen=True)
class IndustryResearchSynthesisNode:
    name: str = "industry_synthesis"

    def __call__(self, state: ResearchState) -> dict:
        request = state["request"]
        bundle = state["analysis_bundle"]
        context = state["analysis_context"]
        industry = _artifact(bundle, AnalysisMethod.INDUSTRY_ANALYSIS)
        peers = _artifact(bundle, AnalysisMethod.PEER_BENCHMARKING)
        scenario_analysis = _artifact(bundle, AnalysisMethod.SCENARIO_ANALYSIS)
        scenarios = [
            value
            if isinstance(value, IndustryScenario)
            else IndustryScenario.model_validate(value)
            for value in context.get("scenarios", [])
        ]
        if len(scenarios) < 2:
            raise ValueError(
                "industry research requires at least two explicit scenarios"
            )
        industry_name = request.industries[0]
        findings = [
            finding for artifact in bundle.artifacts for finding in artifact.findings
        ]
        evidence_ids = list(
            dict.fromkeys(
                evidence_id
                for finding in findings
                for evidence_id in finding.evidence_ids
            )
        )
        limitations = list(
            dict.fromkeys(
                [
                    *bundle.warnings,
                    *(
                        item
                        for artifact in bundle.artifacts
                        for item in artifact.limitations
                    ),
                ]
            )
        ) or ["Only the supplied public evidence was analysed."]
        monitoring = list(
            dict.fromkeys(
                indicator
                for scenario in scenarios
                for indicator in scenario.monitoring_indicators
            )
        )
        report = IndustryResearchReport(
            title=f"{industry_name}经营分化与情景研究",
            industry_name=industry_name,
            as_of_date=request.as_of_date,
            executive_summary=" ".join(
                artifact.summary for artifact in bundle.artifacts
            ),
            value_chain=list(context.get("value_chain", []))
            or ["上游供给", "品牌与生产", "渠道", "终端消费"],
            industry_structure=industry.summary,
            demand_outlook="；".join(
                finding.implication for finding in industry.findings
            ),
            supply_and_competition="；".join(
                finding.statement for finding in industry.findings
            ),
            peer_comparison=peers.summary,
            scenarios=scenarios,
            key_metrics={
                key: str(value)
                for artifact in bundle.artifacts
                for key, value in artifact.metrics.items()
            },
            opportunities=[
                finding.implication for finding in scenario_analysis.findings
            ]
            or ["No evidence-backed opportunity was identified."],
            risks=limitations,
            monitoring_indicators=monitoring,
            evidence_ids=evidence_ids,
            limitations=limitations,
            conclusion=(
                "现有证据支持对高端白酒形成有条件的行业判断。后续应以同业报告、"
                "渠道库存、核心产品价格和终端需求的新证据为触发点，动态调整情景。"
            ),
        )
        return {"industry_research_report": report, "current_stage": self.name}


@dataclass(frozen=True)
class IndustryResearchReviewNode:
    minimum_evidence_records: int = 3
    name: str = "industry_research_review"

    def __call__(self, state: ResearchState) -> dict:
        request = state["request"]
        selection = state["workflow_selection"]
        bundle = state["analysis_bundle"]
        report = state["industry_research_report"]
        issues: list[IndustryResearchReviewIssue] = []
        produced = {item.method for item in bundle.artifacts}
        missing = set(selection.analysis_methods) - produced
        if missing:
            issues.append(
                IndustryResearchReviewIssue(
                    severity=IssueSeverity.HIGH,
                    description="Missing required analysis methods: "
                    + ", ".join(sorted(item.value for item in missing)),
                    recommendation="Run each router-selected industry analysis engine.",
                    target=IndustryResearchRevisionTarget.ANALYSIS,
                )
            )
        if len(bundle.evidence) < self.minimum_evidence_records:
            issues.append(
                IndustryResearchReviewIssue(
                    severity=IssueSeverity.HIGH,
                    description="The evidence set is too small for industry research.",
                    recommendation="Add demand, company, peer, and channel evidence.",
                    target=IndustryResearchRevisionTarget.ANALYSIS,
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
                IndustryResearchReviewIssue(
                    severity=IssueSeverity.HIGH,
                    description="Insufficient evidence for findings: "
                    + ", ".join(insufficient),
                    recommendation="Collect the missing industry or peer evidence.",
                    target=IndustryResearchRevisionTarget.ANALYSIS,
                )
            )
        known = {item.evidence_id for item in bundle.evidence}
        if not set(report.evidence_ids).issubset(known):
            issues.append(
                IndustryResearchReviewIssue(
                    severity=IssueSeverity.CRITICAL,
                    description="The report contains an unknown evidence reference.",
                    recommendation="Remove or resolve unsupported evidence identifiers.",
                    target=IndustryResearchRevisionTarget.SYNTHESIS,
                )
            )
        if request.task_type != TaskType.INDUSTRY_RESEARCH:
            issues.append(
                IndustryResearchReviewIssue(
                    severity=IssueSeverity.CRITICAL,
                    description="The workflow received a non-industry request.",
                    recommendation="Return the request to platform intake.",
                    target=IndustryResearchRevisionTarget.SYNTHESIS,
                )
            )
        if issues:
            result = IndustryResearchReviewResult(
                decision=ReviewDecision.NEED_REVISION,
                issues=issues,
                revision_target=issues[0].target,
                overall_assessment="The industry report is not ready for delivery.",
            )
        else:
            result = IndustryResearchReviewResult(
                decision=ReviewDecision.APPROVED,
                strengths=[
                    "已执行 Router 选定的全部行业分析方法。",
                    "每项情景均列明触发条件和监测指标。",
                    "报告判断可追溯至已登记的公开证据。",
                ],
                overall_assessment=(
                    "委员会同意将本报告作为样本边界明确的公开信息行业研究交付。"
                ),
            )
        return {"industry_research_review": result, "current_stage": self.name}
