"""Markdown delivery for financial anomaly screening and quality review."""

from pathlib import Path

from schemas.financial_risk import (
    AuditTrail,
    FinancialRiskInput,
    FinancialRiskScorecard,
    HumanSignOff,
)
from schemas.platform import EvidenceRecord
from schemas.quality_review import QualityReviewResult


def _display_value(signal_id: str, value: float | None) -> str:
    if value is None:
        return "不适用"
    percentage_signals = {
        "FR-ACCRUAL",
        "FR-AR-GAP",
        "FR-INVENTORY-GAP",
        "FR-MARGIN-PEER",
        "FR-NONRECURRING",
    }
    count_signals = {"FR-EXCHANGE-INQUIRY", "FR-REGULATORY-PENALTY"}
    if signal_id in percentage_signals:
        return f"{value:.2%}"
    if signal_id in count_signals:
        return str(int(value))
    return f"{value:.2f}x"


def render_financial_risk_report(
    data: FinancialRiskInput,
    scorecard: FinancialRiskScorecard,
    evidence: list[EvidenceRecord],
    *,
    quality_review: QualityReviewResult | None = None,
    signoff: HumanSignOff | None = None,
    audit_trail: AuditTrail | None = None,
) -> str:
    triggered = [signal for signal in scorecard.signals if signal.triggered]
    delivery_status = "内部质量复核前草稿"
    if quality_review is not None:
        delivery_status = f"IQR {quality_review.decision.value} / 人工签署待定"
    if signoff is not None and signoff.status.value != "pending":
        delivery_status = (
            "可交付终稿"
            if signoff.status.value == "approved"
            else f"人工签署 {signoff.status.value}"
        )
    lines = [
        f"# {data.company_name}（{data.security_code}）财务异常识别与风险预警报告",
        "",
        "| 报告属性 | 内容 |",
        "| --- | --- |",
        f"| 截止日期 | {data.as_of_date.isoformat()} |",
        f"| 交付状态 | {delivery_status} |",
        f"| 风险评分 | {scorecard.risk_score:.1f} / 100 |",
        f"| 风险等级 | `{scorecard.risk_level.value}` |",
        f"| 触发信号 | {len(triggered)} / {len(scorecard.signals)} |",
        f"| 方法版本 | {scorecard.methodology_version} |",
        "",
        "> 本报告用于财务异常筛查和管理层风险预警，不构成审计意见、"
        "舞弊认定、信用评级或投资建议。异常信号必须结合原始凭证、业务访谈和"
        "专业人员复核。",
        "",
        "## 执行摘要",
        "",
        f"规则引擎识别出 {len(triggered)} 项触发信号，综合风险评分为 "
        f"{scorecard.risk_score:.1f}，等级为 `{scorecard.risk_level.value}`。"
        "该结果表示需要进一步核验的财务与治理信号，不表示公司存在财务舞弊。",
        "",
        "**管理层优先事项：** "
        + (
            "、".join(signal.label for signal in triggered[:4])
            or "未发现高于预设阈值的信号"
        ),
        "",
        "## 财务异常风险信号",
        "",
        "| 原因代码 | 类别 | 指标 | 数值 | 阈值 | 严重程度 |",
        "| --- | --- | --- | ---: | --- | --- |",
    ]
    for signal in scorecard.signals:
        display = _display_value(signal.signal_id, signal.value)
        status = signal.severity.value if signal.triggered else "not_triggered"
        lines.append(
            f"| {signal.signal_id} | {signal.category.value} | {signal.label} | "
            f"{display} | {signal.threshold} | {status} |"
        )
    lines.extend(["", "### 触发信号解释", ""])
    for signal in triggered:
        lines.extend(
            [
                f"#### {signal.label}｜{signal.signal_id}",
                "",
                f"- **事实观察：** {signal.observation}",
                f"- **风险推断：** {signal.interpretation}",
                f"- **证据：** {', '.join(signal.evidence_ids)}",
                "",
            ]
        )
    lines.extend(
        [
            "## 管理行动路线",
            "",
            "| 风险信号 | Owner | Timeline | 建议动作 | KPI / 验证标准 |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for signal in triggered:
        lines.append(
            f"| {signal.label} | {signal.action.owner} | {signal.action.timeline} | "
            f"{'；'.join(signal.action.actions)} | {'；'.join(signal.action.kpis)} |"
        )
    lines.extend(
        [
            "",
            "## 事实、推断与建议边界",
            "",
            "- **事实：** 指标由登记的两期结构化财务数据及监管计数计算。",
            "- **推断：** 阈值触发只说明需要进一步核验，不证明会计处理不当。",
            "- **建议：** Owner、Timeline 和 KPI 是管理建议，需要客户确认后执行。",
            f"- **数据范围：** {data.source_scope}",
            "- **方法边界：** 当前阈值为透明规则，需要根据行业、会计准则和历史样本校准。",
            "",
            "## 内部质量复核",
            "",
        ]
    )
    if quality_review is None:
        lines.append("尚未执行独立质量复核，不得作为正式交付终稿。")
    else:
        passed = sum(check.passed for check in quality_review.checks)
        lines.extend(
            [
                f"- 决策：`{quality_review.decision.value}`",
                f"- 控制通过：{passed}/{len(quality_review.checks)}",
                f"- 证据覆盖率：{quality_review.evidence_coverage:.1%}",
                f"- 可复现：{quality_review.reproducible}",
                f"- 报告一致：{quality_review.report_consistent}",
                f"- 结论：{quality_review.overall_assessment}",
                "",
                "| 控制编号 | 类别 | 结果 | 说明 |",
                "| --- | --- | --- | --- |",
            ]
        )
        for check in quality_review.checks:
            lines.append(
                f"| {check.check_id} | {check.category.value} | "
                f"{'PASS' if check.passed else 'FAIL'} | {check.details} |"
            )
    lines.extend(["", "## 人工签署", ""])
    if signoff is None or signoff.status.value == "pending":
        lines.append("状态：`pending`。自动质量控制通过不能替代项目负责人签署。")
    else:
        lines.extend(
            [
                f"- 状态：`{signoff.status.value}`",
                f"- 复核人：{signoff.reviewer}",
                f"- 时间：{signoff.reviewed_at.isoformat() if signoff.reviewed_at else '—'}",
                f"- 意见：{signoff.comments or '—'}",
            ]
        )
    if audit_trail is not None:
        lines.extend(
            [
                "",
                "## 审计轨迹",
                "",
                f"- Run ID：`{audit_trail.run_id}`",
                f"- Code version：`{audit_trail.code_version}`",
                f"- Input hash：`{audit_trail.input_hash}`",
                f"- Output hash：`{audit_trail.output_hash}`",
            ]
        )
    lines.extend(["", "## 证据附录", ""])
    for item in evidence:
        published = (
            item.published_at.date().isoformat() if item.published_at else "未知"
        )
        lines.append(
            f"- **{item.evidence_id}｜{item.title}**（{item.source_name}，{published}）："
            f"{item.summary}"
        )
    lines.extend(["", "## 方法警示", ""])
    lines.extend(f"- {warning}" for warning in scorecard.warnings)
    return "\n".join(lines).strip() + "\n"


def save_financial_risk_report(content: str, path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target
