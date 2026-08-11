"""Deterministic Markdown rendering for a public-data risk consultation."""

from pathlib import Path

from schemas.advisory import CompanyRiskProfile
from schemas.debate import DebateGateResult, DebateResult
from schemas.platform import AnalysisBundle

_SEVERITY_LABELS = {
    "critical": "极高",
    "high": "高",
    "medium": "中",
    "low": "低",
}


def _label(value: str) -> str:
    return _SEVERITY_LABELS[value]


def _cell(items: list[str]) -> str:
    return "；".join(items).replace("|", "｜") or "—"


def render_risk_advisory_report(
    profile: CompanyRiskProfile,
    analysis: AnalysisBundle,
    gate: DebateGateResult,
    debate: DebateResult | None,
) -> str:
    """Render a decision-ready advisory report from validated structured inputs."""
    priority_items = [
        item
        for item in profile.assessments
        if item.severity.value in {"critical", "high"}
    ]
    priority_names = "、".join(item.category for item in priority_items)
    matrix: dict[tuple[str, str], list[str]] = {}
    for item in profile.assessments:
        matrix.setdefault((item.impact.value, item.likelihood.value), []).append(
            item.category
        )

    lines = [
        f"# {profile.company_name}（{profile.security_code}）公开信息风险咨询报告",
        "",
        "| 报告属性 | 内容 |",
        "| --- | --- |",
        "| 客户议题 | 经营、财务、治理与外部风险诊断 |",
        f"| 分析截止日 | {profile.as_of_date.isoformat()} |",
        f"| 证据基础 | {len(analysis.evidence)} 项公开披露证据 |",
        f"| 优先风险 | {len(priority_items)} 项高优先级议题 |",
        f"| 研究审查 | Debate Gate：{gate.decision.value} |",
        "",
        "## 执行摘要",
        "",
        f"基于截至 {profile.as_of_date.isoformat()} 的公开披露，本次诊断识别出 "
        f"{len(priority_items)} 项应进入管理层近期议程的高优先级风险：{priority_names}。"
        "核心管理命题并非单一经营指标恶化，而是增长、盈利、现金转化与外部约束"
        "之间的联动是否会持续扩大。建议以现金转化和销量—毛利情景作为未来30天"
        "的管理抓手，同时在90天内补齐集团信用敞口与海外连续性压力测试。",
        "",
        "### Partner View｜核心判断",
        "",
        "1. **先管现金，再解释增长。** 收入、利润与经营现金流的背离，需要通过"
        "季度现金桥接和营运资本归因转化为可追责的管理动作。",
        "2. **将销量压力与盈利能力放在同一情景中评估。** 单独追踪销量可能掩盖"
        "促销、产品结构及出口贡献对利润的二阶影响。",
        "3. **把低频尾部风险纳入常态治理。** 集团担保和海外合规当前未必形成"
        "即时损失，但应通过敞口台账、触发阈值和连续性预案降低突发事件成本。",
        "",
        "## 风险优先级二维矩阵",
        "",
        "> 纵轴为潜在影响，横轴为基于当前证据判断的发生可能性；"
        "风险优先级另综合考虑管理紧迫度。",
        "",
        "| 潜在影响 \\ 发生可能性 | 高 | 中 | 低 |",
        "| --- | --- | --- | --- |",
    ]
    for impact in ("high", "medium", "low"):
        lines.append(
            f"| **{_label(impact)}** | "
            + " | ".join(
                _cell(matrix.get((impact, likelihood), []))
                for likelihood in ("high", "medium", "low")
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "### 风险依据与管理含义",
            "",
            "| 风险议题 | 优先级 | 观察事实 | 管理含义 | 证据 / 置信度 |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for item in profile.assessments:
        lines.append(
            f"| {item.category} | {_label(item.severity.value)} | "
            f"{item.observation} | {item.implication} | "
            f"{_cell(item.evidence_ids)} / {item.confidence:.0%} |"
        )

    lines.extend(
        [
            "",
            "## 未来90天行动路线",
            "",
            "| 优先事项 | Owner | Timeline | 管理动作 | KPI / 触发指标 |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for item in profile.assessments:
        lines.append(
            f"| {item.category} | {item.action_owner} | {item.timeline} | "
            f"{_cell(item.mitigation_actions)} | {_cell(item.kpis)} |"
        )

    lines.extend(["", "## 风险监测卡", ""])
    for item in profile.assessments:
        lines.extend(
            [
                f"### {item.category}",
                "",
                f"**定位：** 影响 {_label(item.impact.value)} / 发生可能性 "
                f"{_label(item.likelihood.value)} / 当前优先级 "
                f"{_label(item.severity.value)}",
                "",
                "**监测指标：** " + _cell(item.monitoring_indicators),
                "",
                "**建议动作：** " + _cell(item.mitigation_actions),
                "",
            ]
        )

    lines.extend(["## 韧性与风险缓释因素", ""])
    lines.extend(f"- {item}" for item in profile.resilience_factors)
    lines.extend(
        [
            "",
            "## 委员会挑战与分歧处理",
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
                "**已形成共识**",
                "",
                *(f"- {item}" for item in debate.consensus_findings),
                "",
                "**仍有争议**",
                "",
                *(f"- {item}" for item in debate.disputed_findings),
                "",
                "**未解决问题**",
                "",
                *(f"- {item}" for item in debate.unresolved_issues),
                "",
                "**Moderator结论：** " + debate.moderator_conclusion,
            ]
        )

    lines.extend(["", "## 数据范围、可信边界与待补信息", ""])
    lines.extend(f"- {item}" for item in profile.scope_limitations)
    lines.extend(["", "## 公开证据附录", ""])
    for record in analysis.evidence:
        locator = record.url or "未提供链接"
        published = (
            record.published_at.date().isoformat() if record.published_at else "未知"
        )
        lines.append(
            f"- [{record.evidence_id}] [{record.title}]({locator})，"
            f"{record.source_name}，发布日 {published}。{record.summary}"
        )
    lines.extend(
        [
            "",
            "---",
            "",
            "本报告为研究工程与管理咨询工作流演示，不构成投资建议、审计意见、"
            "信用评级或法律意见。风险判断仅在列明证据和截止日范围内成立。",
            "",
        ]
    )
    return "\n".join(lines)


def save_risk_advisory_report(content: str, path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")
    return output.resolve()
