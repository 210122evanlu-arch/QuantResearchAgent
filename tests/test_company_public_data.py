from datetime import UTC, date, datetime

import pandas as pd
import pytest

from analysis_engines.company import (
    build_company_analysis_context,
    create_company_analysis_registry,
)
from data_sources.company_public import (
    BaoStockCompanyDataProvider,
    CNInfoAnnouncementClient,
    CompanyPublicDataConfig,
    to_baostock_code,
)
from schemas.enums import AnalysisMethod, EvidenceStatus
from schemas.platform import EvidenceRecord


class FakeResult:
    def __init__(
        self,
        frame: pd.DataFrame | None = None,
        error_code: str = "0",
        error_msg: str = "",
    ) -> None:
        self.frame = frame if frame is not None else pd.DataFrame()
        self.error_code = error_code
        self.error_msg = error_msg

    def get_data(self) -> pd.DataFrame:
        return self.frame.copy()


class FakeCompanyAPI:
    def __init__(self) -> None:
        self.logged_out = False

    def login(self) -> FakeResult:
        return FakeResult()

    def logout(self) -> FakeResult:
        self.logged_out = True
        return FakeResult()

    def query_history_k_data_plus(self, code, fields, **kwargs) -> FakeResult:
        dates = pd.bdate_range("2024-07-01", "2025-06-30")
        sequence = pd.Series(range(len(dates)), dtype=float)
        return FakeResult(
            pd.DataFrame(
                {
                    "date": dates.strftime("%Y-%m-%d"),
                    "code": code,
                    "close": 20 + sequence / 20,
                    "pctChg": 0.2 + sequence / 1000,
                    "turn": 1.5,
                    "amount": 1_000_000,
                    "peTTM": 18.0,
                    "pbMRQ": 2.5,
                    "psTTM": 1.2,
                    "pcfNcfTTM": 14.0,
                    "tradestatus": "1",
                }
            )
        )

    @staticmethod
    def _statement(code, year, quarter, values) -> FakeResult:
        if (year, quarter) == (2025, 1):
            return FakeResult(
                pd.DataFrame(
                    {
                        "code": [code],
                        "pubDate": ["2025-04-30"],
                        "statDate": ["2025-03-31"],
                        **{name: [value] for name, value in values.items()},
                    }
                )
            )
        if (year, quarter) == (2025, 2):
            return FakeResult(
                pd.DataFrame(
                    {
                        "code": [code],
                        "pubDate": ["2025-08-30"],
                        "statDate": ["2025-06-30"],
                        **{name: [value * 2] for name, value in values.items()},
                    }
                )
            )
        return FakeResult()

    def query_profit_data(self, *, code, year, quarter) -> FakeResult:
        return self._statement(code, year, quarter, {"roeAvg": 12.5, "npMargin": 5.2})

    def query_balance_data(self, *, code, year, quarter) -> FakeResult:
        return self._statement(
            code, year, quarter, {"currentRatio": 1.3, "liabilityToAsset": 65.0}
        )

    def query_cash_flow_data(self, *, code, year, quarter) -> FakeResult:
        return self._statement(code, year, quarter, {"CFOToOR": 0.11, "CFOToNP": 0.93})

    def query_growth_data(self, *, code, year, quarter) -> FakeResult:
        return self._statement(code, year, quarter, {"YOYNI": 18.0, "YOYAsset": 10.0})


class FakeAnnouncements:
    def search(self, security_code, *, start_date, end_date):
        return [
            EvidenceRecord(
                evidence_id=f"ANN-{security_code}",
                source_type="company_announcement",
                title="Quarterly operating announcement",
                source_name="CNInfo fixture",
                url="https://example.test/announcement.pdf",
                published_at=datetime(2025, 6, 15, tzinfo=UTC),
                retrieved_at=datetime(2025, 6, 30, tzinfo=UTC),
                summary="Fixture official disclosure.",
            )
        ]


class FakeHTTPResponse:
    def __init__(self, payload) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self.payload


class FakeHTTPSession:
    def __init__(self) -> None:
        self.headers = {}
        self.payload = None

    def post(self, url, **kwargs):
        self.payload = kwargs["data"]
        if "topSearch" in url:
            return FakeHTTPResponse([{"code": "002594", "orgId": "gshk0001211"}])
        return FakeHTTPResponse(
            {
                "announcements": [
                    {
                        "announcementId": "123",
                        "announcementTitle": "<em>Annual</em> report",
                        "adjunctUrl": "finalpage/2025-04-01/report.pdf",
                        "announcementTime": 1743436800000,
                    }
                ]
            }
        )


def _package(code="002594.SZ"):
    provider = BaoStockCompanyDataProvider(
        api=FakeCompanyAPI(), announcement_client=FakeAnnouncements()
    )
    return provider.build(
        CompanyPublicDataConfig(
            company_name=f"Fixture {code}",
            security_code=code,
            as_of_date=date(2025, 6, 30),
        )
    )


def test_security_code_conversion_is_explicit() -> None:
    assert to_baostock_code("600000.SH") == "sh.600000"
    assert to_baostock_code("000001.SZ") == "sz.000001"
    with pytest.raises(ValueError, match=r"600000\.SH"):
        to_baostock_code("sh.600000")


def test_provider_builds_point_in_time_package() -> None:
    package = _package()

    assert package.look_ahead_bias_checked is True
    assert len(package.market_metrics) >= 7
    assert len(package.financial_metrics) == 8
    assert {metric.observation_date for metric in package.financial_metrics} == {
        date(2025, 4, 30)
    }
    assert all(
        item.published_at is None or item.published_at.date() <= package.as_of_date
        for item in package.evidence
    )


def test_cninfo_client_preserves_public_locator_and_cutoff() -> None:
    session = FakeHTTPSession()
    client = CNInfoAnnouncementClient(session=session)
    records = client.search(
        "002594.SZ", start_date=date(2025, 1, 1), end_date=date(2025, 6, 30)
    )

    assert records[0].title == "Annual report"
    assert records[0].url == (
        "https://static.cninfo.com.cn/finalpage/2025-04-01/report.pdf"
    )
    assert session.payload["stock"] == "002594,gshk0001211"


def test_company_engines_use_target_and_peer_packages() -> None:
    target = _package("002594.SZ")
    peers = [_package("600104.SH"), _package("601633.SH")]
    context = build_company_analysis_context(target, peers)
    registry = create_company_analysis_registry()
    artifacts = [
        registry.execute(method, context)
        for method in (
            AnalysisMethod.FINANCIAL_STATEMENT_ANALYSIS,
            AnalysisMethod.STRATEGIC_DIAGNOSIS,
            AnalysisMethod.RELATIVE_VALUATION,
            AnalysisMethod.PEER_BENCHMARKING,
        )
    ]

    assert artifacts[1].findings[0].status == EvidenceStatus.INSUFFICIENT
    assert all(
        finding.status == EvidenceStatus.VERIFIED
        for artifact in (artifacts[0], artifacts[2], artifacts[3])
        for finding in artifact.findings
    )
    valuation = artifacts[2]
    assert valuation.metrics["pe_ttm"]["peer_median"] == 18.0
    assert len(context["evidence"]) >= 12
