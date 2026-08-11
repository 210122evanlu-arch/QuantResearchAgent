"""Deterministic Markdown rendering for a public-data risk consultation."""

from pathlib import Path

from schemas.advisory import CompanyRiskProfile
from schemas.debate import DebateGateResult, DebateResult
from schemas.platform import AnalysisBundle


def render_risk_advisory_report(
    profile: CompanyRiskProfile,
    analysis: AnalysisBundle,
    gate: DebateGateResult,
    debate: DebateResult | None,
) -> str:
    lines = [
        f"# {profile.company_name}（{profile.security_code}）公开信息风险咨询报告",
        "",
        f"> 分析截止日：{profile.as_of_date.isoformat()}",
        "> 使用范围：研究与咨询演示，不构成投资建议、审计意见或法律意见。",
        "",
        "## 执行摘要",
        "",
        "本报告以公司正式披露为证据，识别风险信号、缓释因素和待补充信息。"
        "风险等级表示需要监测的优先级，不等同于对公司或证券价值的确定判断。",
        "",
        "## 风险矩阵",
        "",
        "| 风险 | 等级 | 观察事实 | 咨询含义 | 置信度 |",
        "| --- | --- | --- | --- | ---: |",
    ]
    for item in profile.assessments:
        lines.append(
            f"| {item.category} | {item.severity.value} | {item.observation} | "
            f"{item.implication} | {item.confidence:.0%} |"
        )

    lines.extend(["", "## 建议行动与监测指标", ""])
    for item in profile.assessments:
        lines.append(f"### {item.category}")
        lines.append("")
        lines.append("监测：" + "；".join(item.monitoring_indicators))
        lines.append("")
        lines.append("建议：" + "；".join(item.mitigation_actions))
        lines.append("")

    lines.extend(["## 韧性与风险缓释因素", ""])
    lines.extend(f"- {item}" for item in profile.resilience_factors)
    lines.extend(
        [
            "",
            "## Debate Gate 与研究辩论",
            "",
            f"Gate：`{gate.decision.value}`；触发因素："
            + (", ".join(item.value for item in gate.triggers) or "无"),
            "",
        ]
    )
    if debate is None:
        lines.append("本次任务未进入研究辩论。")
    else:
        lines.extend(
            [
                f"讨论轮数：{len(debate.rounds)}；"
                f"是否由硬上限终止：{'是' if debate.stopped_by_limit else '否'}。",
                "",
                "共识：",
                "",
                *(f"- {item}" for item in debate.consensus_findings),
                "",
                "仍有争议：",
                "",
                *(f"- {item}" for item in debate.disputed_findings),
                "",
                "未解决问题：",
                "",
                *(f"- {item}" for item in debate.unresolved_issues),
                "",
                "Moderator结论：" + debate.moderator_conclusion,
            ]
        )

    lines.extend(["", "## 数据范围与限制", ""])
    lines.extend(f"- {item}" for item in profile.scope_limitations)
    lines.extend(["", "## 公开证据", ""])
    for record in analysis.evidence:
        locator = record.url or "未提供链接"
        published = (
            record.published_at.date().isoformat() if record.published_at else "未知"
        )
        lines.append(
            f"- [{record.evidence_id}] [{record.title}]({locator})，"
            f"{record.source_name}，发布日 {published}。{record.summary}"
        )
    lines.append("")
    return "\n".join(lines)


def save_risk_advisory_report(content: str, path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")
    return output.resolve()
