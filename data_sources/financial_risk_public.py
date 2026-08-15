"""Point-in-time BaoStock ratios and CNInfo risk-disclosure assembly."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any, ClassVar, Protocol, cast

import baostock as bs
import pandas as pd

from data_sources.baostock import BaoStockDataError, BaoStockResult, _result_frame
from data_sources.company_public import (
    CNInfoAnnouncementClient,
    CompanyPublicDataError,
    _evidence_id,
    _quarters,
    to_baostock_code,
)
from data_sources.filing_pdf import (
    FilingPDFError,
    FilingPDFExtractor,
    select_latest_annual_report,
)
from schemas.company_filing import FilingExtractionResult, FilingSectionTopic
from schemas.enums import AuditOpinionStatus, IndustryProfile
from schemas.financial_risk import (
    FinancialRiskDataPackage,
    FinancialRiskInput,
    FinancialStatementSnapshot,
    RegulatoryDisclosureSummary,
)
from schemas.platform import EvidenceRecord


class FinancialRiskBaoStockAPI(Protocol):
    def login(self) -> BaoStockResult: ...

    def logout(self) -> BaoStockResult: ...

    def query_profit_data(self, *args: Any, **kwargs: Any) -> BaoStockResult: ...

    def query_balance_data(self, *args: Any, **kwargs: Any) -> BaoStockResult: ...

    def query_cash_flow_data(self, *args: Any, **kwargs: Any) -> BaoStockResult: ...

    def query_growth_data(self, *args: Any, **kwargs: Any) -> BaoStockResult: ...

    def query_operation_data(self, *args: Any, **kwargs: Any) -> BaoStockResult: ...


class FinancialStatementProvider(Protocol):
    def collect(self, config: FinancialRiskPublicConfig) -> FinancialStatementPair: ...


@dataclass(frozen=True)
class FinancialRiskPublicConfig:
    company_name: str
    security_code: str
    as_of_date: date
    industry_profile: IndustryProfile = IndustryProfile.GENERAL
    financial_quarters: int = 12
    disclosure_days: int = 800
    extract_audit_opinion: bool = True

    def __post_init__(self) -> None:
        if not self.company_name.strip():
            raise ValueError("company_name cannot be blank")
        to_baostock_code(self.security_code)
        if not 8 <= self.financial_quarters <= 20:
            raise ValueError("financial_quarters must be between 8 and 20")
        if self.disclosure_days < 30:
            raise ValueError("disclosure_days must be at least 30")


@dataclass(frozen=True)
class FinancialStatementPair:
    current: FinancialStatementSnapshot
    prior: FinancialStatementSnapshot
    evidence: list[EvidenceRecord]
    warnings: list[str]


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _percent(value: Any) -> float | None:
    number = _number(value)
    if number is None:
        return None
    return number / 100 if abs(number) > 1 else number


def _ratio(value: Any) -> float | None:
    number = _number(value)
    if number is None:
        return None
    return number / 100 if abs(number) > 10 else number


def _previous_year_same_date(value: date) -> date:
    try:
        return value.replace(year=value.year - 1)
    except ValueError:
        return value.replace(year=value.year - 1, day=28)


class BaoStockFinancialRiskProvider:
    """Map point-in-time BaoStock ratios into the generic risk-input contract."""

    statement_queries: ClassVar[dict[str, str]] = {
        "profit": "query_profit_data",
        "balance": "query_balance_data",
        "cash_flow": "query_cash_flow_data",
        "growth": "query_growth_data",
        "operation": "query_operation_data",
    }

    def __init__(self, api: FinancialRiskBaoStockAPI | None = None) -> None:
        self.api = api or cast(FinancialRiskBaoStockAPI, bs)

    @staticmethod
    def _frame(result: BaoStockResult, endpoint: str) -> pd.DataFrame:
        try:
            return _result_frame(result, endpoint)
        except BaoStockDataError as exc:
            raise CompanyPublicDataError(str(exc)) from exc

    def collect(self, config: FinancialRiskPublicConfig) -> FinancialStatementPair:
        provider_code = to_baostock_code(config.security_code)
        login = self.api.login()
        if login.error_code != "0":
            raise CompanyPublicDataError(
                f"BaoStock login failed [{login.error_code}]: {login.error_msg}"
            )
        rows: dict[str, dict[date, pd.Series]] = {}
        try:
            for statement, query_name in self.statement_queries.items():
                query = getattr(self.api, query_name)
                statement_rows: dict[date, pd.Series] = {}
                for year, quarter in _quarters(
                    config.as_of_date, config.financial_quarters
                ):
                    frame = self._frame(
                        query(code=provider_code, year=year, quarter=quarter),
                        query_name,
                    )
                    if frame.empty or not {"pubDate", "statDate"}.issubset(frame):
                        continue
                    values = frame.copy()
                    values["pubDate"] = pd.to_datetime(
                        values["pubDate"], errors="coerce"
                    )
                    values["statDate"] = pd.to_datetime(
                        values["statDate"], errors="coerce"
                    )
                    values = values.dropna(subset=["pubDate", "statDate"])
                    values = values.loc[values["pubDate"].dt.date <= config.as_of_date]
                    for _, row in values.iterrows():
                        period = cast(pd.Timestamp, row["statDate"]).date()
                        existing = statement_rows.get(period)
                        if existing is None or row["pubDate"] > existing["pubDate"]:
                            statement_rows[period] = row
                rows[statement] = statement_rows
        finally:
            self.api.logout()
        periods = sorted({period for values in rows.values() for period in values})
        if len(periods) < 2:
            raise CompanyPublicDataError(
                "BaoStock did not return two published financial periods before cutoff"
            )
        current_period = periods[-1]
        same_quarter_prior = _previous_year_same_date(current_period)
        prior_period = (
            same_quarter_prior if same_quarter_prior in periods else periods[-2]
        )
        evidence: list[EvidenceRecord] = []
        current, current_evidence = self._snapshot(
            config, provider_code, current_period, rows
        )
        prior, prior_evidence = self._snapshot(
            config, provider_code, prior_period, rows
        )
        evidence.extend([*current_evidence, *prior_evidence])
        warnings = []
        if prior_period != same_quarter_prior:
            warnings.append(
                "A same-quarter prior-year period was unavailable; the immediately previous published period was used."
            )
        current_debt = current.debt_to_assets
        prior_debt = prior.debt_to_assets
        if (
            current_debt is not None
            and prior_debt is not None
            and min(current_debt, prior_debt) > 0
            and min(current_debt, prior_debt) / max(current_debt, prior_debt) < 0.20
        ):
            current = current.model_copy(update={"debt_to_assets": None})
            prior = prior.model_copy(update={"debt_to_assets": None})
            warnings.append(
                "BaoStock liabilityToAsset changed by more than 5x across comparable periods; the field was withheld pending source validation."
            )
        return FinancialStatementPair(
            current=current,
            prior=prior,
            evidence=evidence,
            warnings=warnings,
        )

    @staticmethod
    def _snapshot(
        config: FinancialRiskPublicConfig,
        provider_code: str,
        period: date,
        rows: dict[str, dict[date, pd.Series]],
    ) -> tuple[FinancialStatementSnapshot, list[EvidenceRecord]]:
        available = {
            statement: values[period]
            for statement, values in rows.items()
            if period in values
        }
        if not available:
            raise CompanyPublicDataError(f"No statement data for {period.isoformat()}")
        publications = [
            cast(pd.Timestamp, row["pubDate"]).date() for row in available.values()
        ]
        evidence: list[EvidenceRecord] = []
        evidence_ids: list[str] = []
        retrieved = datetime.now(UTC)
        for statement, row in available.items():
            publication = cast(pd.Timestamp, row["pubDate"]).date()
            evidence_id = _evidence_id(
                f"BAOSTOCK-RISK-{statement.upper()}",
                config.security_code,
                period.isoformat(),
                publication.isoformat(),
            )
            evidence_ids.append(evidence_id)
            evidence.append(
                EvidenceRecord(
                    evidence_id=evidence_id,
                    source_type=f"financial_{statement}",
                    title=(
                        f"{config.company_name} {statement} indicators for "
                        f"{period.isoformat()}"
                    ),
                    source_name="BaoStock",
                    document_id=(
                        f"baostock:{provider_code}:{statement}:{period.isoformat()}"
                    ),
                    published_at=datetime.combine(
                        publication, datetime.min.time(), tzinfo=UTC
                    ),
                    retrieved_at=retrieved,
                    summary=(
                        "Provider indicators selected only when pubDate was not after "
                        "the engagement cutoff."
                    ),
                )
            )
        empty = pd.Series(dtype=object)
        profit: pd.Series = available.get("profit", empty)
        balance: pd.Series = available.get("balance", empty)
        cash_flow: pd.Series = available.get("cash_flow", empty)
        growth: pd.Series = available.get("growth", empty)
        operation: pd.Series = available.get("operation", empty)
        net_profit = _number(profit.get("netProfit"))
        cash_conversion = _ratio(cash_flow.get("CFOToNP"))
        operating_cash_flow = (
            net_profit * cash_conversion
            if net_profit is not None and cash_conversion is not None
            else None
        )
        return (
            FinancialStatementSnapshot(
                period_end=period,
                publication_date=max(publications),
                revenue=_number(profit.get("MBRevenue")),
                net_profit=net_profit,
                operating_cash_flow=operating_cash_flow,
                gross_margin=_percent(profit.get("gpMargin")),
                cash_conversion_ratio=cash_conversion,
                revenue_growth=_percent(growth.get("YOYRevenue")),
                current_ratio=_ratio(balance.get("currentRatio")),
                return_on_equity=_percent(profit.get("roeAvg")),
                net_profit_margin=_percent(profit.get("npMargin")),
                debt_to_assets=_percent(balance.get("liabilityToAsset")),
                interest_coverage=_ratio(balance.get("EBITToInterest")),
                receivables_days=_number(operation.get("NRTurnDays")),
                inventory_days=_number(operation.get("INVTurnDays")),
                asset_turnover=_ratio(operation.get("AssetTurnRatio")),
                evidence_ids=evidence_ids,
            ),
            evidence,
        )


class TabularFinancialRiskProvider:
    """Load complete point-in-time statement snapshots from a licensed table."""

    required_columns: ClassVar[set[str]] = {
        "security_code",
        "period_end",
        "publication_date",
    }

    def __init__(self, frame: pd.DataFrame, *, source_name: str) -> None:
        if not source_name.strip():
            raise ValueError("source_name cannot be blank")
        missing = self.required_columns - set(frame.columns)
        if missing:
            raise ValueError(
                "financial risk table is missing: " + ", ".join(sorted(missing))
            )
        self.frame = frame.copy()
        self.source_name = source_name

    def collect(self, config: FinancialRiskPublicConfig) -> FinancialStatementPair:
        values = self.frame.loc[
            self.frame["security_code"].astype(str).str.upper() == config.security_code
        ].copy()
        values["period_end"] = pd.to_datetime(values["period_end"], errors="coerce")
        values["publication_date"] = pd.to_datetime(
            values["publication_date"], errors="coerce"
        )
        values = values.dropna(subset=["period_end", "publication_date"])
        values = values.loc[
            values["publication_date"].dt.date <= config.as_of_date
        ].sort_values(["period_end", "publication_date"])
        values = values.drop_duplicates(subset=["period_end"], keep="last")
        if len(values) < 2:
            raise CompanyPublicDataError(
                "The point-in-time table has fewer than two published periods before cutoff"
            )
        current_row = values.iloc[-1]
        current_period = cast(pd.Timestamp, current_row["period_end"]).date()
        same_quarter = values.loc[
            values["period_end"].dt.date == _previous_year_same_date(current_period)
        ]
        prior_row = same_quarter.iloc[-1] if not same_quarter.empty else values.iloc[-2]
        snapshots: list[FinancialStatementSnapshot] = []
        evidence: list[EvidenceRecord] = []
        retrieved = datetime.now(UTC)
        snapshot_fields = set(FinancialStatementSnapshot.model_fields) - {
            "period_end",
            "publication_date",
            "evidence_ids",
        }
        for row in (prior_row, current_row):
            period = cast(pd.Timestamp, row["period_end"]).date()
            publication = cast(pd.Timestamp, row["publication_date"]).date()
            evidence_id = _evidence_id(
                "TABLE-RISK",
                config.security_code,
                self.source_name,
                period.isoformat(),
                publication.isoformat(),
            )
            payload: dict[str, Any] = {
                "period_end": period,
                "publication_date": publication,
                "evidence_ids": [evidence_id],
            }
            for field in snapshot_fields.intersection(row.index):
                value = row[field]
                if pd.notna(value):
                    payload[field] = value
            snapshots.append(FinancialStatementSnapshot.model_validate(payload))
            evidence.append(
                EvidenceRecord(
                    evidence_id=evidence_id,
                    source_type="point_in_time_financial_table",
                    title=f"{config.company_name} standardized financials for {period}",
                    source_name=self.source_name,
                    document_id=(
                        f"table:{config.security_code}:{period}:{publication}"
                    ),
                    published_at=datetime.combine(
                        publication, datetime.min.time(), tzinfo=UTC
                    ),
                    retrieved_at=retrieved,
                    summary=(
                        "Standardized financial fields filtered by publication date; "
                        "source licence and accounting mapping remain the operator's responsibility."
                    ),
                )
            )
        return FinancialStatementPair(
            current=snapshots[1],
            prior=snapshots[0],
            evidence=evidence,
            warnings=[],
        )


def classify_audit_opinion(
    extraction: FilingExtractionResult,
) -> tuple[AuditOpinionStatus, list[str]]:
    """Classify explicit audit wording from extracted annual-report pages."""
    sections = [
        item
        for item in extraction.sections
        if item.topic == FilingSectionTopic.AUDIT_OPINION
    ]
    evidence_ids = [item.evidence_id for item in sections]
    text = "\n".join(item.text for item in sections)
    text_without_unqualified = text.replace("无保留意见", "")
    if any(
        term in text_without_unqualified
        for term in ("保留意见", "否定意见", "无法表示意见")
    ):
        return AuditOpinionStatus.NON_STANDARD, evidence_ids
    if "无保留意见" in text:
        return AuditOpinionStatus.STANDARD_UNQUALIFIED, evidence_ids
    return AuditOpinionStatus.UNKNOWN, evidence_ids


class CNInfoRiskDisclosureCollector:
    """Classify official disclosure titles without inventing full-text conclusions."""

    inquiry_terms = ("问询函", "关注函", "审核问询")
    penalty_terms = (
        "行政处罚",
        "纪律处分",
        "公开谴责",
        "监管警示",
        "监管措施",
    )
    preliminary_penalty_terms = ("事先告知", "拟处罚")
    non_standard_audit_terms = (
        "非标准审计意见",
        "保留意见",
        "否定意见",
        "无法表示意见",
    )
    standard_audit_terms = ("标准无保留审计意见",)

    def __init__(
        self,
        client: CNInfoAnnouncementClient | None = None,
        *,
        filing_extractor: FilingPDFExtractor | None = None,
    ) -> None:
        self.client = client or CNInfoAnnouncementClient(page_size=50, max_pages=20)
        self.filing_extractor = filing_extractor or FilingPDFExtractor()

    def collect(
        self, config: FinancialRiskPublicConfig
    ) -> tuple[RegulatoryDisclosureSummary, list[EvidenceRecord]]:
        records = self.client.search(
            config.security_code,
            start_date=config.as_of_date - timedelta(days=config.disclosure_days),
            end_date=config.as_of_date,
        )
        inquiries = [
            item
            for item in records
            if any(term in item.title for term in self.inquiry_terms)
        ]
        penalties = [
            item
            for item in records
            if any(term in item.title for term in self.penalty_terms)
            and not any(term in item.title for term in self.preliminary_penalty_terms)
        ]
        non_standard = [
            item
            for item in records
            if any(term in item.title for term in self.non_standard_audit_terms)
        ]
        standard = [
            item
            for item in records
            if any(term in item.title for term in self.standard_audit_terms)
        ]
        if non_standard:
            opinion = AuditOpinionStatus.NON_STANDARD
        elif standard:
            opinion = AuditOpinionStatus.STANDARD_UNQUALIFIED
        else:
            opinion = AuditOpinionStatus.UNKNOWN
        full_text_evidence: list[EvidenceRecord] = []
        full_text_audit_ids: list[str] = []
        full_text_warning: str | None = None
        if opinion == AuditOpinionStatus.UNKNOWN and config.extract_audit_opinion:
            try:
                annual_reports = self.client.search_annual_reports(
                    config.security_code,
                    start_date=config.as_of_date
                    - timedelta(days=config.disclosure_days),
                    end_date=config.as_of_date,
                )
                annual_report = select_latest_annual_report(
                    annual_reports, config.as_of_date
                )
                extraction = self.filing_extractor.extract(annual_report)
                opinion, full_text_audit_ids = classify_audit_opinion(extraction)
                known = {item.evidence_id: item for item in extraction.page_evidence}
                full_text_evidence = [
                    known[evidence_id]
                    for evidence_id in full_text_audit_ids
                    if evidence_id in known
                ]
            except (CompanyPublicDataError, FilingPDFError, OSError) as exc:
                full_text_warning = "Audit-opinion full-text extraction failed: " + str(
                    exc
                )
        relevant = list(
            {
                item.evidence_id: item.model_copy(
                    update={
                        "source_type": (
                            "exchange_inquiry"
                            if item in inquiries
                            else "regulatory_action"
                            if item in penalties
                            else "audit_opinion_disclosure"
                        )
                    }
                )
                for item in [
                    *inquiries,
                    *penalties,
                    *non_standard,
                    *standard,
                    *full_text_evidence,
                ]
            }.values()
        )
        warnings = []
        if full_text_warning:
            warnings.append(full_text_warning)
        if opinion == AuditOpinionStatus.UNKNOWN:
            warnings.append(
                "Audit opinion was not confirmed from an explicit CNInfo disclosure title; full-text annual-report extraction is required."
            )
        return (
            RegulatoryDisclosureSummary(
                audit_opinion=opinion,
                exchange_inquiry_count=len(inquiries),
                regulatory_penalty_count=len(penalties),
                audit_opinion_evidence_ids=[
                    item.evidence_id for item in [*non_standard, *standard]
                ]
                + full_text_audit_ids,
                exchange_inquiry_evidence_ids=[item.evidence_id for item in inquiries],
                regulatory_penalty_evidence_ids=[
                    item.evidence_id for item in penalties
                ],
                evidence_ids=[item.evidence_id for item in relevant],
                warnings=warnings,
            ),
            relevant,
        )


class PublicFinancialRiskAssembler:
    """Combine point-in-time financial ratios and official risk disclosures."""

    def __init__(
        self,
        *,
        financial_provider: FinancialStatementProvider | None = None,
        disclosure_collector: CNInfoRiskDisclosureCollector | None = None,
    ) -> None:
        self.financial_provider = financial_provider or BaoStockFinancialRiskProvider()
        self.disclosure_collector = (
            disclosure_collector or CNInfoRiskDisclosureCollector()
        )

    def build(self, config: FinancialRiskPublicConfig) -> FinancialRiskDataPackage:
        statements = self.financial_provider.collect(config)
        disclosures, disclosure_evidence = self.disclosure_collector.collect(config)
        evidence = list(
            {
                item.evidence_id: item
                for item in [*statements.evidence, *disclosure_evidence]
            }.values()
        )
        data = FinancialRiskInput(
            company_name=config.company_name,
            security_code=config.security_code,
            as_of_date=config.as_of_date,
            current=statements.current,
            prior=statements.prior,
            industry_profile=config.industry_profile,
            audit_opinion=disclosures.audit_opinion,
            audit_opinion_evidence_ids=disclosures.audit_opinion_evidence_ids,
            exchange_inquiry_count=disclosures.exchange_inquiry_count,
            exchange_inquiry_evidence_ids=(disclosures.exchange_inquiry_evidence_ids),
            regulatory_penalty_count=disclosures.regulatory_penalty_count,
            regulatory_penalty_evidence_ids=(
                disclosures.regulatory_penalty_evidence_ids
            ),
            source_scope=(
                "Point-in-time BaoStock financial indicators and CNInfo disclosure "
                "titles available by the stated cutoff."
            ),
            data_warnings=[*statements.warnings, *disclosures.warnings],
        )
        return FinancialRiskDataPackage(
            financial_input=data,
            evidence=evidence,
            warnings=[*statements.warnings, *disclosures.warnings],
        )
