"""Markdown delivery for event watchlists and report-refresh decisions."""

from pathlib import Path

from schemas.events import EventIntelligenceResult

_ACTION_LABELS = {
    "no_action": "无需更新",
    "watchlist": "加入观察清单",
    "refresh_report": "触发报告更新",
    "escalate_review": "升级研究委员会复核",
}
_SOURCE_LABELS = {
    "official_disclosure": "公司正式披露",
    "regulatory_source": "监管来源",
    "news": "新闻线索",
}
_DIRECTION_LABELS = {
    "positive": "正向",
    "negative": "负向",
    "mixed": "混合",
    "neutral": "中性",
    "uncertain": "待确认",
}
_CATEGORY_LABELS = {
    "earnings": "业绩与财务",
    "operations": "经营动态",
    "capital_allocation": "资本配置",
    "governance": "公司治理",
    "regulatory": "监管事项",
    "transaction": "交易与重组",
    "litigation": "诉讼仲裁",
    "other": "其他",
}
_MATERIALITY_LABELS = {"critical": "极高", "high": "高", "medium": "中", "low": "低"}


def render_event_intelligence(result: EventIntelligenceResult) -> str:
    lines = [
        '<div align="center">',
        "",
        f"<h1>{result.company_name}事件情报与研究更新提示</h1>",
        "",
        f"<p><strong>{result.security_code}</strong><br>",
        f"监测截止日 {result.as_of_date.isoformat()} · 原报告截止日 "
        f"{result.report_as_of_date.isoformat()}</p>",
        "",
        "</div>",
        "",
        "## 更新决策",
        "",
        f"**建议动作：{_ACTION_LABELS[result.action.value]}** "
        f"(`{result.action.value}`)",
        "",
        result.rationale,
        "",
        "| 事件 | 日期 | 来源属性 | 分类 | 方向 | 重大性 | 处理 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    triggers = set(result.trigger_event_ids)
    for event in result.events:
        handling = "触发更新" if event.event_id in triggers else "观察 / 核实"
        lines.append(
            f"| {event.title} | {event.published_at.date()} | "
            f"{_SOURCE_LABELS[event.source_type.value]} | "
            f"{_CATEGORY_LABELS[event.category.value]} | "
            f"{_DIRECTION_LABELS[event.direction.value]} | "
            f"{_MATERIALITY_LABELS[event.materiality.value]} | {handling} |"
        )
    lines.extend(
        [
            "",
            "## 建议重跑的报告部分",
            "",
            *(f"- `{section}`" for section in result.affected_sections),
            "",
            "## 治理规则",
            "",
            "- 公司公告或监管证据达到高重大性时，触发报告更新。",
            "- 新闻报道在缺少原始披露时仅进入观察清单，不直接改写研究结论。",
            "- 相似标题、相同文档 ID 或相同链接在进入判断前完成去重。",
            f"- 本次共移除 {result.duplicate_count} 项重复事件。",
            "",
            "---",
            "",
            "该结果用于研究更新管理，不构成投资建议；事件解释仍需核对原始文件全文。",
            "",
        ]
    )
    return "\n".join(lines)


def save_event_intelligence(content: str, path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")
    return output.resolve()
