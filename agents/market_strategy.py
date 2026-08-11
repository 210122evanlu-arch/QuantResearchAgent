"""Synthesis and committee nodes for evidence-grounded market strategy."""

from dataclasses import dataclass

from schemas.enums import (
    AnalysisMethod,
    EvidenceStatus,
    IssueSeverity,
    ReviewDecision,
    TaskType,
)
from schemas.market_strategy import (
    ConvictionLevel,
    MarketRegimeAssessment,
    MarketScenario,
    MarketStrategyReport,
    MarketStrategyReviewIssue,
    MarketStrategyReviewResult,
    MarketStrategyRevisionTarget,
    StrategyView,
)
from schemas.platform import AnalysisArtifact, AnalysisBundle
from schemas.state import ResearchState


def _artifact(bundle: AnalysisBundle, method: AnalysisMethod) -> AnalysisArtifact:
    matches = [item for item in bundle.artifacts if item.method == method]
    if len(matches) != 1:
        raise ValueError(
            f"market strategy requires exactly one {method.value} artifact"
        )
    return matches[0]


@dataclass(frozen=True)
class MarketStrategySynthesisNode:
    name: str = "market_synthesis"

    def __call__(self, state: ResearchState) -> dict:
        request = state["request"]
        bundle = state["analysis_bundle"]
        context = state["analysis_context"]
        regime_artifact = _artifact(bundle, AnalysisMethod.MARKET_REGIME_ANALYSIS)
        scenario_artifact = _artifact(bundle, AnalysisMethod.SCENARIO_ANALYSIS)
        assessment = context.get("regime_assessment")
        if not isinstance(assessment, MarketRegimeAssessment):
            assessment = MarketRegimeAssessment.model_validate(assessment)
        scenarios = [
            item
            if isinstance(item, MarketScenario)
            else MarketScenario.model_validate(item)
            for item in context.get("scenarios", [])
        ]
        style_views = [
            item
            if isinstance(item, StrategyView)
            else StrategyView.model_validate(item)
            for item in context.get("style_views", [])
        ]
        sector_views = [
            item
            if isinstance(item, StrategyView)
            else StrategyView.model_validate(item)
            for item in context.get("sector_views", [])
        ]
        if len(scenarios) < 3 or not style_views or not sector_views:
            raise ValueError(
                "market strategy requires three scenarios plus style and sector views"
            )
        findings = [finding for item in bundle.artifacts for finding in item.findings]
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
                    *(value for item in bundle.artifacts for value in item.limitations),
                    f"信号来源：{context.get('signal_provenance', '未登记')}。",
                ]
            )
        )
        conviction = (
            ConvictionLevel.HIGH
            if abs(assessment.score) >= 0.5
            else ConvictionLevel.MEDIUM
            if abs(assessment.score) >= 0.2
            else ConvictionLevel.LOW
        )
        regime_labels = {
            "risk_on": "风险偏好上行",
            "balanced": "均衡",
            "defensive": "防御",
            "transition": "过渡",
        }
        signal_labels = {
            "growth_momentum": "增长动量贡献",
            "liquidity_support": "流动性支持贡献",
            "valuation_attractiveness": "估值吸引力贡献",
            "earnings_momentum": "盈利动量贡献",
            "risk_appetite": "风险偏好贡献",
        }
        report = MarketStrategyReport(
            title="A股市场环境、风格与配置情景研究",
            market_name="中国A股市场",
            as_of_date=request.as_of_date,
            horizon=str(context.get("horizon", "未来3—6个月")),
            regime=assessment.regime,
            conviction=conviction,
            partner_view=(
                f"确定性评分将市场识别为{regime_labels[assessment.regime.value]}环境，总分"
                f"{assessment.score:.3f}。政策与流动性提供支撑，但需求、盈利和风险偏好"
                "并未形成一致上行信号，因此组合应保留再平衡空间而非押注单一路径。"
            ),
            key_signals={
                **{
                    signal_labels[key]: f"{value:+.3f}"
                    for key, value in assessment.signal_contributions.items()
                },
                **{
                    key: str(value)
                    for item in bundle.artifacts
                    for key, value in item.metrics.items()
                },
            },
            macro_environment=regime_artifact.summary,
            liquidity_and_policy="".join(
                finding.implication for finding in regime_artifact.findings
            ),
            valuation_and_earnings="".join(
                finding.statement for finding in regime_artifact.findings
            ),
            style_views=style_views,
            sector_views=sector_views,
            scenarios=scenarios,
            portfolio_implications=[
                finding.implication for finding in scenario_artifact.findings
            ],
            monitoring_indicators=list(context.get("monitoring_indicators", [])),
            risks=limitations,
            evidence_ids=evidence_ids,
            limitations=limitations,
            conclusion=(
                "当前策略结论是条件性的配置框架，而非收益保证。只有在增长、流动性、"
                "盈利、估值和风险偏好信号同步变化后，才应调整市场环境判断。"
            ),
        )
        return {"market_strategy_report": report, "current_stage": self.name}


@dataclass(frozen=True)
class MarketStrategyReviewNode:
    minimum_evidence_records: int = 3
    name: str = "market_review"

    def __call__(self, state: ResearchState) -> dict:
        request = state["request"]
        selection = state["workflow_selection"]
        bundle = state["analysis_bundle"]
        report = state["market_strategy_report"]
        context = state["analysis_context"]
        issues: list[MarketStrategyReviewIssue] = []
        produced = {item.method for item in bundle.artifacts}
        missing = set(selection.analysis_methods) - produced
        if missing:
            issues.append(
                MarketStrategyReviewIssue(
                    severity=IssueSeverity.HIGH,
                    description="Missing router-selected market analysis methods.",
                    recommendation="Run both regime and scenario analysis engines.",
                    target=MarketStrategyRevisionTarget.ANALYSIS,
                )
            )
        if len(bundle.evidence) < self.minimum_evidence_records:
            issues.append(
                MarketStrategyReviewIssue(
                    severity=IssueSeverity.HIGH,
                    description="The market evidence set is too small.",
                    recommendation="Add macro, policy, and market-structure evidence.",
                    target=MarketStrategyRevisionTarget.ANALYSIS,
                )
            )
        insufficient = [
            finding.finding_id
            for item in bundle.artifacts
            for finding in item.findings
            if finding.status == EvidenceStatus.INSUFFICIENT
        ]
        if insufficient:
            issues.append(
                MarketStrategyReviewIssue(
                    severity=IssueSeverity.HIGH,
                    description="Some strategy findings lack sufficient evidence.",
                    recommendation="Refresh the affected signals or reduce conviction.",
                    target=MarketStrategyRevisionTarget.ANALYSIS,
                )
            )
        known = {item.evidence_id for item in bundle.evidence}
        if not set(report.evidence_ids).issubset(known):
            issues.append(
                MarketStrategyReviewIssue(
                    severity=IssueSeverity.CRITICAL,
                    description="The strategy report has an unknown evidence reference.",
                    recommendation="Resolve or remove the unsupported evidence ID.",
                    target=MarketStrategyRevisionTarget.SYNTHESIS,
                )
            )
        if request.task_type != TaskType.MARKET_STRATEGY:
            issues.append(
                MarketStrategyReviewIssue(
                    severity=IssueSeverity.CRITICAL,
                    description="The workflow received a non-market-strategy request.",
                    recommendation="Return the request to platform intake.",
                    target=MarketStrategyRevisionTarget.SYNTHESIS,
                )
            )
        if not context.get("signal_provenance"):
            issues.append(
                MarketStrategyReviewIssue(
                    severity=IssueSeverity.HIGH,
                    description="Market-signal provenance is not registered.",
                    recommendation="Record provider, cutoff, licence, and transformations.",
                    target=MarketStrategyRevisionTarget.ANALYSIS,
                )
            )
        if issues:
            review = MarketStrategyReviewResult(
                decision=ReviewDecision.NEED_REVISION,
                issues=issues,
                revision_target=issues[0].target,
                overall_assessment="The market strategy is not ready for delivery.",
            )
        else:
            review = MarketStrategyReviewResult(
                decision=ReviewDecision.APPROVED,
                strengths=[
                    "市场环境标签由有界信号和固定权重确定。",
                    "三项情景的概率、触发条件和配置含义均已显式列示。",
                    "官方事实、策略推断和离线信号边界保持分离。",
                ],
                overall_assessment="委员会批准将其作为边界明确的市场策略演示。",
            )
        return {"market_strategy_review": review, "current_stage": self.name}
