"""Live company research with annual-report PDF extraction and DeepSeek analysis."""

import argparse
import json
from datetime import date, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from agents.company_filing import analyse_company_filing
from analysis_engines.company import (
    build_company_analysis_context,
    create_company_analysis_registry,
)
from data_sources.company_public import (
    BaoStockCompanyDataProvider,
    CNInfoAnnouncementClient,
    CompanyPublicDataConfig,
)
from data_sources.filing_pdf import FilingPDFExtractor, select_latest_annual_report
from graph.company_research import build_company_research_workflow
from llm import get_default_llm
from schemas.enums import TaskType
from schemas.platform import ResearchRequest


def run_filing_company_research(
    *,
    as_of_date: date,
    report_path: str | Path,
):
    cninfo = CNInfoAnnouncementClient(page_size=50)
    provider = BaoStockCompanyDataProvider(announcement_client=cninfo)
    target = provider.build(
        CompanyPublicDataConfig(
            company_name="比亚迪股份有限公司",
            security_code="002594.SZ",
            as_of_date=as_of_date,
            announcement_days=365,
        )
    )
    peers = [
        provider.build(
            CompanyPublicDataConfig(
                company_name=name,
                security_code=code,
                as_of_date=as_of_date,
                announcement_days=1,
            )
        )
        for name, code in (
            ("上海汽车集团股份有限公司", "600104.SH"),
            ("长城汽车股份有限公司", "601633.SH"),
        )
    ]
    annual_reports = cninfo.search_annual_reports(
        "002594.SZ",
        start_date=as_of_date - timedelta(days=900),
        end_date=as_of_date,
    )
    annual_report = select_latest_annual_report(annual_reports, as_of_date)
    extraction = FilingPDFExtractor().extract(annual_report)
    filing_analysis = analyse_company_filing(extraction, get_default_llm())
    context = build_company_analysis_context(
        target,
        peers,
        filing_extraction=extraction,
        filing_analysis=filing_analysis,
    )
    workflow = build_company_research_workflow(
        create_company_analysis_registry(), report_path=report_path
    )
    request = ResearchRequest(
        task_type=TaskType.COMPANY_RESEARCH,
        question="研究比亚迪的盈利质量、业务模式、竞争力、同业表现与相对估值。",
        companies=["比亚迪股份有限公司"],
        securities=["002594.SZ"],
        as_of_date=as_of_date,
        public_data_only=True,
        debate_requested=False,
    )
    return workflow.invoke(
        {
            "request": request,
            "analysis_context": context,
            "revision_count": 0,
            "max_revisions": 1,
        }
    )


def _jsonable(value: Any) -> Any:
    """Convert the LangGraph result into a durable research artifact."""
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (date, Path)):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def write_research_artifact(result: dict[str, Any], output: Path) -> Path:
    """Persist the complete evidence-to-report state for downstream renderers."""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(_jsonable(result), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output.resolve()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of-date", type=date.fromisoformat, default=date.today())
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("reports/company_research/byd_filing_deepseek_report.md"),
    )
    parser.add_argument(
        "--artifact",
        type=Path,
        default=Path("reports/artifacts/byd_company_research_filing.json"),
    )
    args = parser.parse_args()
    result = run_filing_company_research(
        as_of_date=args.as_of_date,
        report_path=args.report,
    )
    extraction = result["analysis_context"]["company_filing_extraction"]
    print(
        f"Annual report: {extraction.title}; pages={extraction.page_count}; "
        f"sections={len(extraction.sections)}"
    )
    print(
        "Company research decision: " + result["company_research_review"].decision.value
    )
    print(f"Report: {result['report_markdown_path']}")
    artifact = write_research_artifact(result, args.artifact)
    print(f"Artifact: {artifact}")


if __name__ == "__main__":
    main()
