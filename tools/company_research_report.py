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
    status = review.decision.value.upper()
    lines = [
        f"# {report.title}",
        "",
        f"> Security: {report.security_code} | As of: {report.as_of_date.isoformat()} | Review: **{status}**",
        "> Public-information research prototype; not investment advice.",
        "",
        "## Executive Summary",
        "",
        report.executive_summary,
        "",
        "## Company and Business Model",
        "",
        report.business_model,
        "",
        "### Competitive Position",
        "",
        report.competitive_position,
        "",
        "## Financial Quality",
        "",
        report.financial_quality,
        "",
        "## Valuation and Peer Comparison",
        "",
        f"**Valuation:** {report.valuation}",
        "",
        f"**Peers:** {report.peer_comparison}",
        "",
        "## Catalysts",
        "",
        *(f"- {item}" for item in report.catalysts),
        "",
        "## Risks and Monitoring",
        "",
        *(f"- {item}" for item in report.risks),
        "",
        "### Monitoring indicators",
        "",
        *(f"- {item}" for item in report.monitoring_indicators),
        "",
        "## Research Committee",
        "",
        review.overall_assessment,
        "",
    ]
    if debate is not None:
        lines.extend(
            [
                "### Debate synthesis",
                "",
                debate.moderator_conclusion,
                "",
                *(f"- Unresolved: {item}" for item in debate.unresolved_issues),
                "",
            ]
        )
    lines.extend(["## Limitations", ""])
    lines.extend(f"- {item}" for item in report.limitations)
    lines.extend(["", "## Conclusion", "", report.conclusion, "", "## Evidence", ""])
    referenced = set(report.evidence_ids)
    for item in analysis.evidence:
        if item.evidence_id not in referenced:
            continue
        locator = item.url or item.document_id or "No public locator supplied"
        lines.append(
            f"- **[{item.evidence_id}] {item.title}** — {item.source_name}; "
            f"{item.summary} ({locator})"
        )
    lines.append("")
    return "\n".join(lines)


def save_company_research_report(content: str, path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")
    return output.resolve()
