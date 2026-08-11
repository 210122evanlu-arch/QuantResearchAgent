"""Deterministic Markdown renderer for listed-company research."""

from pathlib import Path

from schemas.company_research import CompanyResearchReport, CompanyResearchReviewResult
from schemas.debate import DebateResult
from schemas.platform import AnalysisBundle


def render_company_research_report(
    report: CompanyResearchReport,
    analysis: AnalysisBundle,
    review: CompanyResearchReviewResult,
    debate: DebateResult | None = None,
) -> str:
    """Render an evidence-grounded, committee-ready company research note."""
    status = review.decision.value.upper()
    lines = [
        '<div align="center">',
        "",
        f"<h1>{report.title}</h1>",
        "",
        f"<p><strong>{report.company_name} · {report.security_code}</strong><br>",
        f"评估截止日 {report.as_of_date.isoformat()} · 委员会状态 {status}</p>",
        "",
        "</div>",
        "",
        "| 报告属性 | 内容 |",
        "| --- | --- |",
        f"| 公司 / 证券代码 | {report.company_name} / {report.security_code} |",
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
            "## 商业模式与竞争位置",
            "",
            report.business_model,
            "",
            "### 竞争位置",
            "",
            report.competitive_position,
            "",
            "## 财务质量",
            "",
            report.financial_quality,
            "",
            "## 估值框架与同业比较",
            "",
            f"**估值框架：** {report.valuation}",
            "",
            f"**同业比较：** {report.peer_comparison}",
            "",
            "## 催化因素",
            "",
            *(f"- {item}" for item in report.catalysts),
            "",
            "## 风险与跟踪指标",
            "",
            *(f"- {item}" for item in report.risks),
            "",
            "### 跟踪指标",
            "",
            *(f"- {item}" for item in report.monitoring_indicators),
            "",
            "## 研究委员会",
            "",
            review.overall_assessment,
            "",
        ]
    )
    if debate is not None:
        lines.extend(
            [
                "### 辩论结论",
                "",
                debate.moderator_conclusion,
                "",
                *(f"- 待解决：{item}" for item in debate.unresolved_issues),
                "",
            ]
        )
    lines.extend(["## 局限性", ""])
    lines.extend(f"- {item}" for item in report.limitations)
    lines.extend(["", "## 研究结论", "", report.conclusion, "", "## 证据附录", ""])
    referenced = set(report.evidence_ids)
    for item in analysis.evidence:
        if item.evidence_id not in referenced:
            continue
        locator = item.url or item.document_id or "未提供公开定位信息"
        lines.append(
            f"- **[{item.evidence_id}] [{item.title}]({locator})** — "
            f"{item.source_name}；{item.summary}"
        )
    lines.extend(
        [
            "",
            "---",
            "",
            "本报告为公开信息研究与研究工程演示，不构成投资建议、估值承诺或"
            "证券买卖依据。结论仅在列明证据及评估截止日范围内成立。",
            "",
        ]
    )
    return "\n".join(lines)


def save_company_research_report(content: str, path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")
    return output.resolve()
