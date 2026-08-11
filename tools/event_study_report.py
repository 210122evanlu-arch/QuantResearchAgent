"""Markdown renderer for statistical event-study delivery."""

from pathlib import Path

from schemas.event_study import (
    EventStudyReport,
    EventStudyResult,
    EventStudyReviewResult,
)
from schemas.platform import EvidenceRecord


def render_event_study_report(
    report: EventStudyReport,
    result: EventStudyResult,
    review: EventStudyReviewResult,
    evidence: list[EvidenceRecord],
) -> str:
    status = "已批准" if review.decision.value == "approved" else "需修订"
    lines = [
        '<div align="center">',
        "",
        f"<h1>{report.title}</h1>",
        "",
        f"<p><strong>{result.design.security_code}</strong><br>",
        f"事件日 {result.design.event_date.isoformat()} · 评估截止日 "
        f"{report.as_of_date.isoformat()} · 委员会状态 {status}</p>",
        "",
        "</div>",
        "",
        "## 执行摘要",
        "",
        report.executive_summary,
        "",
        "## 事件与研究假设",
        "",
        report.event_background,
        "",
        "研究假设：目标事件发布前后不存在显著异常收益；若 CAR 的双侧检验拒绝该假设，"
        "则事件窗口内存在统计异常，但仍不自动等于因果归因。",
        "",
        "## 方法与估计设计",
        "",
        report.methodology,
        "",
        "| 事件窗口 | 观察数 | CAR | AAR | t-stat | p-value | 显著 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for window in result.window_results:
        t_stat = f"{window.t_stat:.3f}" if window.t_stat is not None else "N/A"
        p_value = (
            "<0.0001"
            if window.p_value is not None and window.p_value < 0.0001
            else f"{window.p_value:.4f}"
            if window.p_value is not None
            else "N/A"
        )
        lines.append(
            f"| [{window.start_day}, {window.end_day}] | {window.observations} | "
            f"{window.cumulative_abnormal_return:.2%} | "
            f"{window.average_abnormal_return:.2%} | "
            f"{t_stat} | {p_value} | "
            f"{'是' if window.significant else '否'} |"
        )
    lines.extend(
        [
            "",
            "### 逐日异常收益",
            "",
            "| 相对日 | 交易日 | 证券收益 | 基准收益 | 期望收益 | AR |",
            "| ---: | --- | ---: | ---: | ---: | ---: |",
            *(
                f"| {item.relative_day} | {item.trading_date} | "
                f"{item.security_return:.2%} | {item.benchmark_return:.2%} | "
                f"{item.expected_return:.2%} | {item.abnormal_return:.2%} |"
                for item in result.daily_abnormal_returns
            ),
            "",
            "## 研究发现",
            "",
            *(f"- {item}" for item in report.findings),
            "",
            "## 稳健性与污染检查",
            "",
            report.robustness_summary,
            "",
            *(f"- {item}" for item in report.risks),
            "",
            "## 研究委员会",
            "",
            review.overall_assessment,
            "",
            *(f"- {item}" for item in review.strengths),
            "",
            "## 局限性与可信边界",
            "",
            *(f"- {item}" for item in report.limitations),
            "",
            "## 结论",
            "",
            report.conclusion,
            "",
            "## 证据附录",
            "",
        ]
    )
    referenced = set(report.evidence_ids)
    for record in evidence:
        if record.evidence_id in referenced:
            locator = record.url or record.document_id or "未提供公开定位信息"
            lines.append(
                f"- **[{record.evidence_id}] [{record.title}]({locator})** — "
                f"{record.source_name}：{record.summary}"
            )
    lines.extend(
        [
            "",
            "---",
            "",
            "本报告用于研究工程与统计方法演示，不构成投资建议。离线收益夹具不得被解释为"
            "示例证券的真实历史市场表现。",
            "",
        ]
    )
    return "\n".join(lines)


def save_event_study_report(content: str, path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")
    return output.resolve()
