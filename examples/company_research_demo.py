"""Offline BYD fixture proving the generic company-research workflow."""

from datetime import date, datetime
from pathlib import Path

from analysis_engines.router import AnalysisEngineRegistry
from graph.company_research import build_company_research_workflow
from schemas.enums import AnalysisMethod, EvidenceStatus, TaskType
from schemas.platform import (
    AnalysisArtifact,
    EvidenceRecord,
    ResearchFinding,
    ResearchRequest,
)


def _evidence() -> list[EvidenceRecord]:
    retrieved = datetime(2026, 8, 8)
    return [
        EvidenceRecord(
            evidence_id="BYD-CR-E1",
            source_type="annual_report",
            title="BYD 2025 Annual Report",
            source_name="BYD disclosure fixture",
            document_id="fixture://byd/annual-report-2025",
            published_at=datetime(2026, 3, 28),
            retrieved_at=retrieved,
            summary="Revenue growth, profitability, cash flow, and segment disclosures.",
        ),
        EvidenceRecord(
            evidence_id="BYD-CR-E2",
            source_type="market_data",
            title="BYD market and valuation snapshot",
            source_name="Public market-data fixture",
            document_id="fixture://byd/market-snapshot",
            retrieved_at=retrieved,
            summary="Price, valuation multiples, and historical trading range.",
        ),
        EvidenceRecord(
            evidence_id="BYD-CR-E3",
            source_type="peer_disclosure",
            title="Peer operating and valuation comparison",
            source_name="Public peer-disclosure fixture",
            document_id="fixture://byd/peer-comparison",
            retrieved_at=retrieved,
            summary="Comparable growth, margin, return, and valuation indicators.",
        ),
        EvidenceRecord(
            evidence_id="BYD-CR-E4",
            source_type="company_announcement",
            title="BYD production and sales announcement",
            source_name="BYD disclosure fixture",
            document_id="fixture://byd/sales-announcement",
            retrieved_at=retrieved,
            summary="Recent production and sales momentum disclosure.",
        ),
    ]


def _finding(identifier: str, statement: str, implication: str, evidence: str):
    return ResearchFinding(
        finding_id=identifier,
        statement=statement,
        implication=implication,
        evidence_ids=[evidence],
        status=EvidenceStatus.VERIFIED,
        confidence=0.85,
    )


def _engine(method: AnalysisMethod):
    fixtures = {
        AnalysisMethod.FINANCIAL_STATEMENT_ANALYSIS: AnalysisArtifact(
            method=method,
            title="Financial quality",
            summary="Scale continued to expand, while margin and cash conversion require quarterly monitoring.",
            findings=[
                _finding(
                    "BYD-CR-F1",
                    "Revenue scale expanded in the supplied annual-report evidence.",
                    "Operating leverage and cash conversion determine the quality of growth.",
                    "BYD-CR-E1",
                )
            ],
            metrics={"revenue_growth": "monitor", "cash_conversion": "monitor"},
            limitations=["The fixture does not replace audited line-item extraction."],
        ),
        AnalysisMethod.STRATEGIC_DIAGNOSIS: AnalysisArtifact(
            method=method,
            title="Business and competitive position",
            summary="Vertical integration and product breadth support scale, but price competition increases execution pressure.",
            findings=[
                _finding(
                    "BYD-CR-F2",
                    "The business combines vehicle, battery, and overseas expansion capabilities.",
                    "Integrated capabilities can support resilience if capital discipline is maintained.",
                    "BYD-CR-E4",
                )
            ],
            metrics={"sales_momentum": "quarterly"},
            limitations=[
                "Channel inventory and model-level economics are not in the fixture."
            ],
        ),
        AnalysisMethod.RELATIVE_VALUATION: AnalysisArtifact(
            method=method,
            title="Relative valuation",
            summary="Valuation should be interpreted as a scenario range rather than a single-point target.",
            findings=[
                _finding(
                    "BYD-CR-F3",
                    "The supplied snapshot supports relative-multiple comparison.",
                    "Earnings delivery and peer-multiple changes can materially alter implied value.",
                    "BYD-CR-E2",
                )
            ],
            metrics={"pe_band": "scenario", "ev_ebitda_band": "scenario"},
            assumptions=["Comparable accounting definitions are required."],
            limitations=["No investment target price is produced from fixture data."],
        ),
        AnalysisMethod.PEER_BENCHMARKING: AnalysisArtifact(
            method=method,
            title="Peer benchmark",
            summary="The peer set should compare growth, margin, returns, cash conversion, and valuation on aligned definitions.",
            findings=[
                _finding(
                    "BYD-CR-F4",
                    "Peer evidence provides a multidimensional benchmark.",
                    "A premium is defensible only when operating outcomes persistently exceed peers.",
                    "BYD-CR-E3",
                )
            ],
            metrics={"peer_growth_rank": "monitor", "peer_margin_rank": "monitor"},
            limitations=["The fixture peer set is illustrative."],
        ),
    }

    def execute(_context):
        return fixtures[method]

    return execute


def run_company_research_demo(report_path: str | Path | None = None):
    registry = AnalysisEngineRegistry()
    for method in (
        AnalysisMethod.FINANCIAL_STATEMENT_ANALYSIS,
        AnalysisMethod.STRATEGIC_DIAGNOSIS,
        AnalysisMethod.RELATIVE_VALUATION,
        AnalysisMethod.PEER_BENCHMARKING,
    ):
        registry.register(method, _engine(method))
    target = (
        Path(report_path)
        if report_path
        else (
            Path(__file__).resolve().parents[1]
            / "reports"
            / "company_research"
            / "byd_company_research_demo.md"
        )
    )
    workflow = build_company_research_workflow(registry, report_path=target)
    request = ResearchRequest(
        task_type=TaskType.COMPANY_RESEARCH,
        question="Assess BYD's financial quality, competitive position, and valuation.",
        objective="Produce an evidence-grounded public-company research report.",
        companies=["BYD Company Limited"],
        securities=["002594.SZ"],
        topics=["financial_quality", "competitive_position", "valuation"],
        as_of_date=date(2026, 8, 8),
        public_data_only=True,
        debate_requested=False,
    )
    return workflow.invoke(
        {
            "request": request,
            "analysis_context": {"evidence": _evidence()},
            "revision_count": 0,
            "max_revisions": 2,
        }
    )


if __name__ == "__main__":
    result = run_company_research_demo()
    print(
        f"Company research workflow: {result['company_research_review'].decision.value}"
    )
    print(f"Report: {result['report_markdown_path']}")
