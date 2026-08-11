"""Markdown renderer for committee-ready market strategy reports."""

from pathlib import Path

from schemas.market_strategy import MarketStrategyReport, MarketStrategyReviewResult
from schemas.platform import AnalysisBundle

_REGIME_LABELS = {
    "risk_on": "风险偏好上行",
    "balanced": "均衡",
    "defensive": "防御",
    "transition": "过渡",
}
_STANCE_LABELS = {
    "overweight": "超配",
    "neutral": "中性",
    "underweight": "低配",
}
_CONVICTION_LABELS = {"low": "低", "medium": "中", "high": "高"}


def render_market_strategy_report(
    report: MarketStrategyReport,
    analysis: AnalysisBundle,
    review: MarketStrategyReviewResult,
) -> str:
    status = "已批准" if review.decision.value == "approved" else "需修订"
    lines = [
        '<div align="center">',
        "",
        f"<h1>{report.title}</h1>",
        "",
        f"<p><strong>{report.market_name}</strong><br>",
        f"评估截止日 {report.as_of_date.isoformat()} · 展望期 {report.horizon} · "
        f"委员会状态 {status}</p>",
        "",
        "</div>",
        "",
        "## Partner View",
        "",
        report.partner_view,
        "",
        "| 核心判断 | 结论 |",
        "| --- | --- |",
        f"| 市场环境 | {_REGIME_LABELS[report.regime.value]} |",
        f"| 策略置信度 | {_CONVICTION_LABELS[report.conviction.value]} |",
        f"| 配置周期 | {report.horizon} |",
        f"| 证据数量 | {len(report.evidence_ids)} |",
        "",
        "### 关键信号仪表板",
        "",
        "| 信号 | 当前读数 |",
        "| --- | ---: |",
        *(f"| {key} | {value} |" for key, value in report.key_signals.items()),
        "",
        "## 宏观、政策与市场环境",
        "",
        report.macro_environment,
        "",
        f"**流动性与政策：** {report.liquidity_and_policy}",
        "",
        f"**估值与盈利：** {report.valuation_and_earnings}",
        "",
        "## 风格与行业配置矩阵",
        "",
        "### 风格观点",
        "",
        "| 风格 | 立场 | 判断依据 | 催化剂 | 主要风险 |",
        "| --- | --- | --- | --- | --- |",
        *(
            f"| {item.segment} | {_STANCE_LABELS[item.stance.value]} | "
            f"{item.rationale} | {'；'.join(item.catalysts)} | "
            f"{'；'.join(item.risks)} |"
            for item in report.style_views
        ),
        "",
        "### 行业观点",
        "",
        "| 行业方向 | 立场 | 判断依据 | 催化剂 | 主要风险 |",
        "| --- | --- | --- | --- | --- |",
        *(
            f"| {item.segment} | {_STANCE_LABELS[item.stance.value]} | "
            f"{item.rationale} | {'；'.join(item.catalysts)} | "
            f"{'；'.join(item.risks)} |"
            for item in report.sector_views
        ),
        "",
        "## 三情景策略矩阵",
        "",
        "| 情景 | 概率 | 触发条件 | 市场含义 | 优先暴露 |",
        "| --- | ---: | --- | --- | --- |",
        *(
            f"| {item.name} | {item.probability:.0%} | "
            f"{'；'.join(item.triggers)} | {'；'.join(item.market_implications)} | "
            f"{'；'.join(item.preferred_exposures)} |"
            for item in report.scenarios
        ),
        "",
        "## 组合含义与监测清单",
        "",
        "### 组合含义",
        "",
        *(f"- {item}" for item in report.portfolio_implications),
        "",
        "### 监测指标",
        "",
        *(f"- {item}" for item in report.monitoring_indicators),
        "",
        "## 研究委员会",
        "",
        review.overall_assessment,
        "",
        *(f"- {item}" for item in review.strengths),
        "",
        "## 风险与可信边界",
        "",
        *(f"- {item}" for item in report.risks),
        "",
        "## 结论",
        "",
        report.conclusion,
        "",
        "## 证据附录",
        "",
    ]
    referenced = set(report.evidence_ids)
    for item in analysis.evidence:
        if item.evidence_id in referenced:
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
            "本报告用于市场研究工程演示，不构成投资建议、资产配置承诺或收益保证。"
            "离线信号评分不代表实时市场状态。",
            "",
        ]
    )
    return "\n".join(lines)


def save_market_strategy_report(content: str, path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")
    return output.resolve()
