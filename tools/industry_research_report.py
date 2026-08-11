"""Deterministic Markdown renderer for evidence-grounded industry research."""

from pathlib import Path

from schemas.industry_research import (
    IndustryResearchReport,
    IndustryResearchReviewResult,
)
from schemas.platform import AnalysisBundle


def render_industry_research_report(
    report: IndustryResearchReport,
    analysis: AnalysisBundle,
    review: IndustryResearchReviewResult,
) -> str:
    """Render a committee-ready industry note with traceable evidence."""
    status = "已批准" if review.decision.value == "approved" else "需修订"
    lines = [
        '<div align="center">',
        "",
        f"<h1>{report.title}</h1>",
        "",
        f"<p><strong>{report.industry_name}</strong><br>",
        f"评估截止日 {report.as_of_date.isoformat()} · 委员会状态 {status}</p>",
        "",
        "</div>",
        "",
        "| 报告属性 | 内容 |",
        "| --- | --- |",
        f"| 行业范围 | {report.industry_name} |",
        f"| 评估截止日 | {report.as_of_date.isoformat()} |",
        f"| 委员会状态 | {status} |",
        f"| 已引用证据 | {len(report.evidence_ids)} 项 |",
        "",
        "## 执行摘要",
        "",
        report.executive_summary,
    ]
    if report.key_metrics:
        lines.extend(
            [
                "",
                "### 关键指标快照",
                "",
                "| 指标 | 当前观察 |",
                "| --- | --- |",
                *(f"| {key} | {value} |" for key, value in report.key_metrics.items()),
            ]
        )
    lines.extend(
        [
            "",
            "## 产业链与价值分配",
            "",
            " → ".join(report.value_chain),
            "",
            report.industry_structure,
            "",
            "## 需求、供给与竞争格局",
            "",
            f"**需求展望：** {report.demand_outlook}",
            "",
            f"**供给与竞争：** {report.supply_and_competition}",
            "",
            "### 同业比较",
            "",
            report.peer_comparison,
            "",
            "## 情景矩阵",
            "",
            "| 情景 | 触发条件 | 行业影响 | 监测指标 |",
            "| --- | --- | --- | --- |",
            *(
                f"| {scenario.name} | {scenario.trigger} | "
                f"{'；'.join(scenario.implications)} | "
                f"{'；'.join(scenario.monitoring_indicators)} |"
                for scenario in report.scenarios
            ),
            "",
            "## 机会、风险与监测",
            "",
            "### 机会",
            "",
            *(f"- {item}" for item in report.opportunities),
            "",
            "### 风险",
            "",
            *(f"- {item}" for item in report.risks),
            "",
            "### 持续监测指标",
            "",
            *(f"- {item}" for item in report.monitoring_indicators),
            "",
            "## 研究委员会",
            "",
            review.overall_assessment,
            "",
            *(f"- 优点：{item}" for item in review.strengths),
            "",
            "## 局限性与适用边界",
            "",
            *(f"- {item}" for item in report.limitations),
            "",
            "## 研究结论",
            "",
            report.conclusion,
            "",
            "## 证据附录",
            "",
        ]
    )
    referenced = set(report.evidence_ids)
    for item in analysis.evidence:
        if item.evidence_id not in referenced:
            continue
        locator = item.url or item.document_id or "未提供公开定位信息"
        lines.append(
            f"- **[{item.evidence_id}] [{item.title}]({locator})** — "
            f"{item.source_name}：{item.summary}"
        )
    lines.extend(
        [
            "",
            "---",
            "",
            "本报告为公开信息研究与研究工程演示，不构成投资建议、估值承诺或证券买卖依据。"
            "结论仅在列明证据、样本范围与评估截止日内成立。",
            "",
        ]
    )
    return "\n".join(lines)


def save_industry_research_report(content: str, path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")
    return output.resolve()
