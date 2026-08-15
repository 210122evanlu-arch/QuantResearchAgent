"""Licensed synthetic fixture for financial anomaly screening and IQR."""

from datetime import UTC, date, datetime
from pathlib import Path

from graph.financial_risk import build_financial_risk_workflow
from schemas.enums import TaskType
from schemas.financial_risk import FinancialRiskInput, FinancialStatementSnapshot
from schemas.platform import EvidenceRecord, ResearchRequest

AS_OF_DATE = date(2026, 4, 30)


def _evidence() -> list[EvidenceRecord]:
    retrieved = datetime(2026, 4, 30, tzinfo=UTC)
    return [
        EvidenceRecord(
            evidence_id="DEMO-FR-E1",
            source_type="licensed_synthetic_fixture",
            title="示例智造2025年度结构化财务数据",
            source_name="QuantResearchAgent synthetic fixture",
            document_id="DEMO-2025",
            published_at=datetime(2026, 3, 31, tzinfo=UTC),
            retrieved_at=retrieved,
            summary=(
                "收入、净利润、经营现金流、资产负债、应收、存货、毛利率和"
                "非经常性损益的合成演示口径。"
            ),
        ),
        EvidenceRecord(
            evidence_id="DEMO-FR-E2",
            source_type="licensed_synthetic_fixture",
            title="示例智造2024年度结构化财务数据",
            source_name="QuantResearchAgent synthetic fixture",
            document_id="DEMO-2024",
            published_at=datetime(2025, 3, 31, tzinfo=UTC),
            retrieved_at=retrieved,
            summary="用于同比基准的上一年度合成财务口径。",
        ),
    ]


def _input() -> FinancialRiskInput:
    return FinancialRiskInput(
        company_name="示例智造股份有限公司",
        security_code="DEMO001",
        as_of_date=AS_OF_DATE,
        current=FinancialStatementSnapshot(
            period_end=date(2025, 12, 31),
            publication_date=date(2026, 3, 31),
            revenue=1_080,
            net_profit=92,
            operating_cash_flow=38,
            total_assets=1_420,
            accounts_receivable=310,
            inventory=275,
            current_assets=560,
            current_liabilities=630,
            interest_bearing_debt=410,
            cash_and_equivalents=105,
            gross_margin=0.34,
            non_recurring_profit=36,
            evidence_ids=["DEMO-FR-E1"],
        ),
        prior=FinancialStatementSnapshot(
            period_end=date(2024, 12, 31),
            publication_date=date(2025, 3, 31),
            revenue=1_000,
            net_profit=88,
            operating_cash_flow=82,
            total_assets=1_180,
            accounts_receivable=190,
            inventory=180,
            current_assets=505,
            current_liabilities=520,
            interest_bearing_debt=300,
            cash_and_equivalents=125,
            gross_margin=0.27,
            non_recurring_profit=8,
            evidence_ids=["DEMO-FR-E2"],
        ),
        peer_gross_margin_median=0.265,
        audit_opinion="standard_unqualified",
        exchange_inquiry_count=1,
        regulatory_penalty_count=0,
        source_scope=(
            "本案例为可公开分发的合成财务夹具，不对应任何真实上市公司；"
            "用于验证指标、路由、质量复核和报告契约。"
        ),
    )


def run_financial_anomaly_risk_demo(report_path: str | Path | None = None):
    target = report_path or (
        Path(__file__).resolve().parents[1]
        / "reports"
        / "advisory"
        / "financial_anomaly_risk_demo.md"
    )
    workflow = build_financial_risk_workflow(
        report_path=target,
        code_version="portfolio-demo",
    )
    request = ResearchRequest(
        task_type=TaskType.CORPORATE_ADVISORY,
        question="识别财务报表异常信号，并形成管理层风险预警和整改路线。",
        companies=["示例智造股份有限公司"],
        securities=["DEMO001"],
        topics=["financial_anomaly", "financial_risk"],
        as_of_date=AS_OF_DATE,
    )
    return workflow.invoke(
        {
            "request": request,
            "financial_risk_input": _input(),
            "financial_risk_evidence": _evidence(),
            "revision_count": 0,
            "max_revisions": 2,
        }
    )


if __name__ == "__main__":
    result = run_financial_anomaly_risk_demo()
    scorecard = result["financial_risk_scorecard"]
    review = result["quality_review_result"]
    print("Financial anomaly screening: passed")
    print("Risk score:", scorecard.risk_score)
    print("Risk level:", scorecard.risk_level.value)
    print("Reason codes:", ", ".join(scorecard.reason_codes))
    print("IQR:", review.decision.value)
    print("Human sign-off:", result["human_signoff"].status.value)
    print("Deliverable:", result["report_markdown_path"])
