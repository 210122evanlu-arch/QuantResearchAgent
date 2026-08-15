from datetime import UTC, date, datetime

import pandas as pd

from data_sources.financial_risk_public import (
    BaoStockFinancialRiskProvider,
    CNInfoRiskDisclosureCollector,
    FinancialRiskPublicConfig,
    PublicFinancialRiskAssembler,
    TabularFinancialRiskProvider,
    classify_audit_opinion,
)
from schemas.company_filing import (
    FilingExtractionResult,
    FilingPageSection,
    FilingSectionTopic,
)
from schemas.enums import AuditOpinionStatus, IndustryProfile
from schemas.platform import EvidenceRecord
from tools.financial_risk import build_audit_trail, screen_financial_anomalies
from tools.financial_risk_report import render_financial_risk_report
from tools.quality_review import run_quality_review


class FakeResult:
    def __init__(self, frame=None, error_code="0", error_msg="") -> None:
        self.frame = frame if frame is not None else pd.DataFrame()
        self.error_code = error_code
        self.error_msg = error_msg

    def get_data(self):
        return self.frame.copy()


class FakeRiskAPI:
    def login(self):
        return FakeResult()

    def logout(self):
        return FakeResult()

    @staticmethod
    def _row(code, year, quarter, values):
        if quarter != 4 or year not in {2024, 2025}:
            return FakeResult()
        publication = f"{year + 1}-03-31"
        return FakeResult(
            pd.DataFrame(
                {
                    "code": [code],
                    "pubDate": [publication],
                    "statDate": [f"{year}-12-31"],
                    **{key: [value] for key, value in values[year].items()},
                }
            )
        )

    def query_profit_data(self, *, code, year, quarter):
        return self._row(
            code,
            year,
            quarter,
            {
                2024: {
                    "netProfit": 80,
                    "MBRevenue": 1000,
                    "gpMargin": 28,
                    "roeAvg": 15,
                    "npMargin": 8,
                },
                2025: {
                    "netProfit": 90,
                    "MBRevenue": 1100,
                    "gpMargin": 26,
                    "roeAvg": 9,
                    "npMargin": 5,
                },
            },
        )

    def query_balance_data(self, *, code, year, quarter):
        return self._row(
            code,
            year,
            quarter,
            {
                2024: {
                    "currentRatio": 1.2,
                    "liabilityToAsset": 62,
                    "EBITToInterest": 4.0,
                },
                2025: {
                    "currentRatio": 0.85,
                    "liabilityToAsset": 74,
                    "EBITToInterest": 1.6,
                },
            },
        )

    def query_cash_flow_data(self, *, code, year, quarter):
        return self._row(
            code,
            year,
            quarter,
            {2024: {"CFOToNP": 1.1}, 2025: {"CFOToNP": 0.55}},
        )

    def query_growth_data(self, *, code, year, quarter):
        return self._row(
            code,
            year,
            quarter,
            {2024: {"YOYRevenue": 12}, 2025: {"YOYRevenue": 10}},
        )

    def query_operation_data(self, *, code, year, quarter):
        return self._row(
            code,
            year,
            quarter,
            {
                2024: {
                    "NRTurnDays": 60,
                    "INVTurnDays": 80,
                    "AssetTurnRatio": 1.0,
                },
                2025: {
                    "NRTurnDays": 90,
                    "INVTurnDays": 120,
                    "AssetTurnRatio": 0.7,
                },
            },
        )


class FakeCNInfo:
    def search(self, security_code, *, start_date, end_date):
        retrieved = datetime(2026, 4, 30, tzinfo=UTC)
        titles = [
            "关于收到交易所年报问询函的公告",
            "关于受到监管警示的公告",
            "董事会关于非标准审计意见的专项说明",
            "普通经营公告",
        ]
        return [
            EvidenceRecord(
                evidence_id=f"CN-{index}",
                source_type="company_announcement",
                title=title,
                source_name="CNInfo fixture",
                url=f"https://example.test/{index}.pdf",
                published_at=datetime(2026, 4, index, tzinfo=UTC),
                retrieved_at=retrieved,
                summary="Official disclosure title fixture.",
            )
            for index, title in enumerate(titles, start=1)
        ]


def _config():
    return FinancialRiskPublicConfig(
        company_name="示例制造",
        security_code="000001.SZ",
        as_of_date=date(2026, 4, 30),
        industry_profile=IndustryProfile.MANUFACTURING,
    )


def test_baostock_adapter_selects_two_published_same_quarter_periods() -> None:
    pair = BaoStockFinancialRiskProvider(FakeRiskAPI()).collect(_config())

    assert pair.current.period_end == date(2025, 12, 31)
    assert pair.prior.period_end == date(2024, 12, 31)
    assert pair.current.publication_date == date(2026, 3, 31)
    assert pair.current.cash_conversion_ratio == 0.55
    assert pair.current.debt_to_assets == 0.74
    assert pair.current.receivables_days == 90
    assert all(
        item.published_at.date() <= _config().as_of_date for item in pair.evidence
    )


def test_cninfo_classifier_separates_inquiry_penalty_and_audit_status() -> None:
    summary, evidence = CNInfoRiskDisclosureCollector(FakeCNInfo()).collect(_config())

    assert summary.audit_opinion == AuditOpinionStatus.NON_STANDARD
    assert summary.exchange_inquiry_count == 1
    assert summary.regulatory_penalty_count == 1
    assert len(evidence) == 3
    assert {item.source_type for item in evidence} == {
        "exchange_inquiry",
        "regulatory_action",
        "audit_opinion_disclosure",
    }


def test_public_assembler_feeds_point_in_time_risk_engine() -> None:
    assembler = PublicFinancialRiskAssembler(
        financial_provider=BaoStockFinancialRiskProvider(FakeRiskAPI()),
        disclosure_collector=CNInfoRiskDisclosureCollector(FakeCNInfo()),
    )

    package = assembler.build(_config())
    scorecard = screen_financial_anomalies(package.financial_input)

    assert package.financial_input.audit_opinion == AuditOpinionStatus.NON_STANDARD
    assert scorecard.data_coverage >= 0.5
    assert "FR-CASH-CONVERSION" in scorecard.reason_codes
    assert "FR-AUDIT-OPINION" in scorecard.reason_codes
    assert "FR-INTEREST-COVERAGE" in scorecard.reason_codes
    trail = build_audit_trail(package.financial_input, scorecard, code_version="test")
    draft = render_financial_risk_report(
        package.financial_input,
        scorecard,
        package.evidence,
        audit_trail=trail,
    )
    review = run_quality_review(
        package.financial_input,
        scorecard,
        package.evidence,
        draft,
        trail,
    )
    assert review.decision.value == "passed"


def test_tabular_provider_enforces_publication_cutoff_and_full_fields() -> None:
    frame = pd.DataFrame(
        [
            {
                "security_code": "000001.SZ",
                "period_end": "2024-12-31",
                "publication_date": "2025-03-31",
                "revenue": 100,
                "net_profit": 10,
                "operating_cash_flow": 11,
                "total_assets": 150,
                "accounts_receivable": 20,
                "inventory": 25,
                "gross_margin": 0.30,
            },
            {
                "security_code": "000001.SZ",
                "period_end": "2025-12-31",
                "publication_date": "2026-03-31",
                "revenue": 110,
                "net_profit": 9,
                "operating_cash_flow": 5,
                "total_assets": 175,
                "accounts_receivable": 35,
                "inventory": 40,
                "gross_margin": 0.26,
            },
            {
                "security_code": "000001.SZ",
                "period_end": "2026-03-31",
                "publication_date": "2026-05-01",
                "revenue": 40,
                "net_profit": 4,
            },
        ]
    )

    pair = TabularFinancialRiskProvider(
        frame, source_name="Licensed point-in-time fixture"
    ).collect(_config())

    assert pair.current.period_end == date(2025, 12, 31)
    assert pair.current.accounts_receivable == 35
    assert pair.prior.period_end == date(2024, 12, 31)
    assert all(
        item.published_at.date() <= _config().as_of_date for item in pair.evidence
    )


def test_full_text_audit_opinion_does_not_misread_unqualified_wording() -> None:
    page = EvidenceRecord(
        evidence_id="PAGE-AUDIT",
        source_type="annual_report_page",
        title="Audit opinion page",
        source_name="Fixture",
        published_at=datetime(2026, 3, 31, tzinfo=UTC),
        retrieved_at=datetime(2026, 4, 1, tzinfo=UTC),
        page_number=1,
        summary="Audit opinion.",
    )
    extraction = FilingExtractionResult(
        source_evidence_id="ANNUAL",
        title="Annual report",
        source_url="https://example.test/annual.pdf",
        local_path="fixture.pdf",
        sha256="a" * 64,
        page_count=1,
        extracted_characters=100,
        sections=[
            FilingPageSection(
                evidence_id=page.evidence_id,
                topic=FilingSectionTopic.AUDIT_OPINION,
                page_number=1,
                matched_keywords=["无保留意见"],
                text="审计意见为标准无保留意见，财务报表在重大方面公允反映。" * 3,
            )
        ],
        page_evidence=[page],
    )

    status, evidence_ids = classify_audit_opinion(extraction)

    assert status == AuditOpinionStatus.STANDARD_UNQUALIFIED
    assert evidence_ids == ["PAGE-AUDIT"]
