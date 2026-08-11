"""Execution, synthesis, and committee nodes for statistical event studies."""

from dataclasses import dataclass

from schemas.enums import IssueSeverity, ReviewDecision, TaskType
from schemas.event_study import (
    EventStudyDesign,
    EventStudyReport,
    EventStudyReviewIssue,
    EventStudyReviewResult,
    EventStudyRevisionTarget,
)
from schemas.state import ResearchState
from tools.event_study import run_event_study


@dataclass(frozen=True)
class EventStudyExecutionNode:
    name: str = "event_execution"

    def __call__(self, state: ResearchState) -> dict:
        context = state["analysis_context"]
        design = context.get("event_study_design")
        if design is None:
            raise ValueError("event study requires event_study_design")
        if not isinstance(design, EventStudyDesign):
            design = EventStudyDesign.model_validate(design)
        returns = context.get("returns")
        if returns is None:
            raise ValueError("event study requires returns")
        result = run_event_study(
            returns,
            design,
            contaminated=bool(context.get("contaminated", False)),
        )
        return {"event_study_result": result, "current_stage": self.name}


@dataclass(frozen=True)
class EventStudySynthesisNode:
    name: str = "event_synthesis"

    def __call__(self, state: ResearchState) -> dict:
        request = state["request"]
        result = state["event_study_result"]
        context = state["analysis_context"]
        evidence = context.get("evidence", [])
        evidence_ids = [
            item.evidence_id if hasattr(item, "evidence_id") else item["evidence_id"]
            for item in evidence
        ]
        if not evidence_ids:
            raise ValueError("event study report requires event evidence")
        windows = []
        for item in result.window_results:
            if item.p_value is None:
                windows.append(
                    f"窗口 [{item.start_day}, {item.end_day}] 无法计算显著性。"
                )
                continue
            p_value = "<0.0001" if item.p_value < 0.0001 else f"={item.p_value:.4f}"
            windows.append(
                f"窗口 [{item.start_day}, {item.end_day}] 的累计异常收益为 "
                f"{item.cumulative_abnormal_return:.2%}，p{p_value}。"
            )
        provenance = str(context.get("return_data_provenance", "未登记"))
        limitations = [
            "市场模型依赖估计窗口稳定性，不能排除未观测风险因子。",
            "CAR 标准误采用估计期残差波动率近似，正式研究应进一步检验横截面与事件聚集问题。",
            f"收益数据来源：{provenance}。",
        ]
        if result.contaminated:
            limitations.append("事件窗口存在重叠事件，结果不能单独归因于目标事件。")
        report = EventStudyReport(
            title=f"{result.design.company_name}{result.design.event_title}事件研究",
            as_of_date=request.as_of_date,
            executive_summary=(
                "本研究使用市场模型评估公告窗口内的异常收益。"
                + " ".join(windows)
                + " 统计结果必须结合数据来源、窗口污染和经济机制解释。"
            ),
            event_background=(
                f"目标事件为“{result.design.event_title}”，事件日为"
                f"{result.design.event_date.isoformat()}，证券代码为"
                f"{result.design.security_code}。"
            ),
            methodology=(
                f"以{result.design.benchmark_name}为基准，估计窗口为"
                f"{result.design.estimation_window}，共"
                f"{result.estimation_observations}个交易日；alpha={result.alpha:.6f}，"
                f"beta={result.beta:.4f}，残差标准差={result.residual_std:.4%}。"
            ),
            findings=windows,
            robustness_summary=(
                "同时报告多个预先声明窗口，并检查交易日完整性、事件日匹配和重叠事件。"
            ),
            risks=list(result.warnings) or ["未发现已登记的事件窗口污染。"],
            limitations=limitations,
            evidence_ids=evidence_ids,
            conclusion=(
                "该结果用于验证事件研究方法和工作流；只有在接入经许可的真实点时收益"
                "数据并复核重叠事件后，才能形成关于该证券实际市场反应的结论。"
            ),
        )
        return {"event_study_report": report, "current_stage": self.name}


@dataclass(frozen=True)
class EventStudyReviewNode:
    minimum_estimation_observations: int = 60
    name: str = "event_review"

    def __call__(self, state: ResearchState) -> dict:
        request = state["request"]
        result = state["event_study_result"]
        report = state["event_study_report"]
        context = state["analysis_context"]
        issues: list[EventStudyReviewIssue] = []
        if request.task_type != TaskType.EVENT_STUDY:
            issues.append(
                EventStudyReviewIssue(
                    severity=IssueSeverity.CRITICAL,
                    description="The workflow received a non-event-study request.",
                    recommendation="Return the request to platform intake.",
                    target=EventStudyRevisionTarget.SYNTHESIS,
                )
            )
        if result.estimation_observations < self.minimum_estimation_observations:
            issues.append(
                EventStudyReviewIssue(
                    severity=IssueSeverity.HIGH,
                    description="The estimation window is too short for committee approval.",
                    recommendation="Provide at least 60 clean pre-event observations.",
                    target=EventStudyRevisionTarget.EXECUTION,
                )
            )
        if result.contaminated:
            issues.append(
                EventStudyReviewIssue(
                    severity=IssueSeverity.CRITICAL,
                    description="A potentially overlapping event contaminates the event window.",
                    recommendation="Change the window, model both events, or qualify attribution.",
                    target=EventStudyRevisionTarget.EXECUTION,
                )
            )
        if result.design.event_date > request.as_of_date:
            issues.append(
                EventStudyReviewIssue(
                    severity=IssueSeverity.CRITICAL,
                    description="The event date is after the research cutoff date.",
                    recommendation="Correct the event or cutoff date.",
                    target=EventStudyRevisionTarget.EXECUTION,
                )
            )
        known = {
            item.evidence_id if hasattr(item, "evidence_id") else item["evidence_id"]
            for item in context.get("evidence", [])
        }
        if not set(report.evidence_ids).issubset(known):
            issues.append(
                EventStudyReviewIssue(
                    severity=IssueSeverity.CRITICAL,
                    description="The report contains an unknown evidence reference.",
                    recommendation="Resolve or remove the unsupported evidence identifier.",
                    target=EventStudyRevisionTarget.SYNTHESIS,
                )
            )
        if not context.get("return_data_provenance"):
            issues.append(
                EventStudyReviewIssue(
                    severity=IssueSeverity.HIGH,
                    description="Return-data provenance is not registered.",
                    recommendation="Record provider, licence, adjustment, and cutoff details.",
                    target=EventStudyRevisionTarget.EXECUTION,
                )
            )
        if issues:
            review = EventStudyReviewResult(
                decision=ReviewDecision.NEED_REVISION,
                issues=issues,
                revision_target=issues[0].target,
                overall_assessment="The event study is not ready for delivery.",
            )
        else:
            review = EventStudyReviewResult(
                decision=ReviewDecision.APPROVED,
                strengths=[
                    "事件、估计窗口和事件窗口均已预先结构化。",
                    "异常收益、CAR 和显著性由确定性代码计算。",
                    "报告明确区分真实公告证据与离线收益夹具。",
                ],
                overall_assessment="委员会批准将其作为方法边界明确的事件研究演示。",
            )
        return {"event_study_review": review, "current_stage": self.name}
