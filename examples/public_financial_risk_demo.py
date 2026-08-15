"""Live keyless financial-risk screen using BaoStock and CNInfo."""

import argparse
from datetime import date
from pathlib import Path

from data_sources.financial_risk_public import (
    FinancialRiskPublicConfig,
    PublicFinancialRiskAssembler,
)
from graph.financial_risk import build_financial_risk_workflow
from schemas.enums import IndustryProfile, TaskType
from schemas.platform import ResearchRequest


def run_public_financial_risk(
    *,
    company_name: str,
    security_code: str,
    as_of_date: date,
    industry_profile: IndustryProfile,
    report_path: str | Path,
):
    package = PublicFinancialRiskAssembler().build(
        FinancialRiskPublicConfig(
            company_name=company_name,
            security_code=security_code,
            as_of_date=as_of_date,
            industry_profile=industry_profile,
        )
    )
    request = ResearchRequest(
        task_type=TaskType.CORPORATE_ADVISORY,
        question=f"识别{company_name}截至指定日期的财务异常和监管风险信号。",
        companies=[company_name],
        securities=[security_code],
        topics=["financial_anomaly", "financial_risk"],
        as_of_date=as_of_date,
        public_data_only=True,
    )
    workflow = build_financial_risk_workflow(
        report_path=report_path,
        code_version="public-data-live",
    )
    return workflow.invoke(
        {
            "request": request,
            "financial_risk_input": package.financial_input,
            "financial_risk_evidence": package.evidence,
            "revision_count": 0,
            "max_revisions": 1,
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--company-name", required=True)
    parser.add_argument("--security-code", required=True)
    parser.add_argument("--as-of-date", type=date.fromisoformat, default=date.today())
    parser.add_argument(
        "--industry-profile",
        type=IndustryProfile,
        choices=list(IndustryProfile),
        default=IndustryProfile.GENERAL,
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("reports/advisory/public_financial_risk.md"),
    )
    args = parser.parse_args()
    result = run_public_financial_risk(
        company_name=args.company_name,
        security_code=args.security_code.upper(),
        as_of_date=args.as_of_date,
        industry_profile=args.industry_profile,
        report_path=args.report,
    )
    scorecard = result["financial_risk_scorecard"]
    print("Risk score:", scorecard.risk_score)
    print("Risk level:", scorecard.risk_level.value)
    print("Data coverage:", f"{scorecard.data_coverage:.1%}")
    print("Threshold profile:", scorecard.threshold_profile)
    print("IQR:", result["quality_review_result"].decision.value)
    print("Human sign-off:", result["human_signoff"].status.value)
    print("Report:", result["report_markdown_path"])


if __name__ == "__main__":
    main()
