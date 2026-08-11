"""Business-facing risk-consulting demo with a decision-ready deliverable."""

from pathlib import Path
from typing import TypedDict

from examples.byd_risk_advisory_demo import run_byd_risk_advisory_demo


class BusinessScenarioSummary(TypedDict):
    client_mandate: str
    company: str
    as_of_date: str
    high_priority_risks: list[str]
    management_focus: list[str]
    committee_synthesis: str
    report_path: str


def run_business_risk_consulting_demo(
    report_path: str | Path | None = None,
) -> BusinessScenarioSummary:
    """Run a listed-company risk mandate and return its business-level summary."""
    state, _ = run_byd_risk_advisory_demo(report_path)
    profile = state["risk_profile"]
    debate = state["debate_result"]
    high_priority = [
        assessment.category
        for assessment in profile.assessments
        if assessment.severity.value == "high"
    ]
    final_round = debate.rounds[-1].moderator
    return {
        "client_mandate": "上市公司经营、财务、治理与外部风险诊断",
        "company": profile.company_name,
        "as_of_date": profile.as_of_date.isoformat(),
        "high_priority_risks": high_priority,
        "management_focus": final_round.unresolved_issues,
        "committee_synthesis": final_round.synthesis,
        "report_path": state["report_markdown_path"],
    }


if __name__ == "__main__":
    result = run_business_risk_consulting_demo()
    print("Business scenario: listed-company risk consulting")
    print("Company:", result["company"])
    print("As of:", result["as_of_date"])
    print("Priority risks:", " / ".join(result["high_priority_risks"]))
    print("Committee synthesis:", result["committee_synthesis"])
    print("Deliverable:", result["report_path"])
