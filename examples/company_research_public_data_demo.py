"""Keyless company-research demo using BaoStock and CNInfo public data."""

import argparse
from datetime import date
from pathlib import Path

from analysis_engines.company import (
    build_company_analysis_context,
    create_company_analysis_registry,
)
from data_sources.company_public import (
    BaoStockCompanyDataProvider,
    CNInfoAnnouncementClient,
    CompanyPublicDataConfig,
)
from graph.company_research import build_company_research_workflow
from schemas.enums import TaskType
from schemas.platform import ResearchRequest


def _peer(value: str) -> tuple[str, str]:
    try:
        name, code = value.split("=", maxsplit=1)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("peer must use NAME=000000.SZ") from exc
    return name.strip(), code.strip().upper()


def run_public_company_research(
    *,
    company_name: str,
    security_code: str,
    peers: list[tuple[str, str]],
    as_of_date: date,
    report_path: str | Path,
):
    provider = BaoStockCompanyDataProvider(
        announcement_client=CNInfoAnnouncementClient()
    )
    target = provider.build(
        CompanyPublicDataConfig(
            company_name=company_name,
            security_code=security_code,
            as_of_date=as_of_date,
        )
    )
    peer_packages = [
        provider.build(
            CompanyPublicDataConfig(
                company_name=name,
                security_code=code,
                as_of_date=as_of_date,
                announcement_days=1,
            )
        )
        for name, code in peers
    ]
    workflow = build_company_research_workflow(
        create_company_analysis_registry(), report_path=report_path
    )
    request = ResearchRequest(
        task_type=TaskType.COMPANY_RESEARCH,
        question=(
            f"Assess {company_name}'s financial quality, competitive position, "
            "peer standing, and relative valuation."
        ),
        companies=[company_name],
        securities=[security_code],
        as_of_date=as_of_date,
        public_data_only=True,
        debate_requested=False,
    )
    return workflow.invoke(
        {
            "request": request,
            "analysis_context": build_company_analysis_context(target, peer_packages),
            "revision_count": 0,
            "max_revisions": 0,
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--company-name", default="BYD Company Limited")
    parser.add_argument("--security-code", default="002594.SZ")
    parser.add_argument("--peer", action="append", type=_peer, default=[])
    parser.add_argument("--as-of-date", type=date.fromisoformat, default=date.today())
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("reports/company_research/byd_public_data_report.md"),
    )
    args = parser.parse_args()
    peers = args.peer or [
        ("SAIC Motor", "600104.SH"),
        ("Great Wall Motor", "601633.SH"),
    ]
    result = run_public_company_research(
        company_name=args.company_name,
        security_code=args.security_code.upper(),
        peers=peers,
        as_of_date=args.as_of_date,
        report_path=args.report,
    )
    review = result["company_research_review"]
    print(f"Company research decision: {review.decision.value}")
    print(f"Report: {result['report_markdown_path']}")


if __name__ == "__main__":
    main()
