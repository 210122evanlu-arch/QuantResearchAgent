"""Free public-market and disclosure collection for company research."""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any, ClassVar, Protocol, cast

import baostock as bs
import pandas as pd
import requests

from data_sources.baostock import (
    BaoStockAPI,
    BaoStockDataError,
    BaoStockResult,
    _result_frame,
)
from schemas.company_data import CompanyPublicDataPackage, ObservedMetric
from schemas.platform import EvidenceRecord


class CompanyPublicDataError(RuntimeError):
    """Raised when a source cannot provide a valid point-in-time package."""


class CompanyBaoStockAPI(BaoStockAPI, Protocol):
    def query_balance_data(self, *args: Any, **kwargs: Any) -> BaoStockResult: ...

    def query_cash_flow_data(self, *args: Any, **kwargs: Any) -> BaoStockResult: ...

    def query_growth_data(self, *args: Any, **kwargs: Any) -> BaoStockResult: ...


class HTTPResponse(Protocol):
    status_code: int

    def raise_for_status(self) -> None: ...

    def json(self) -> Any: ...


class HTTPSession(Protocol):
    headers: dict[str, str]

    def post(self, url: str, **kwargs: Any) -> HTTPResponse: ...


@dataclass(frozen=True)
class CompanyPublicDataConfig:
    company_name: str
    security_code: str
    as_of_date: date
    history_days: int = 370
    financial_quarters: int = 8
    announcement_days: int = 365

    def __post_init__(self) -> None:
        if not self.company_name.strip():
            raise ValueError("company_name cannot be blank")
        if not _is_security_code(self.security_code):
            raise ValueError("security_code must look like 600000.SH or 000001.SZ")
        if self.history_days < 30:
            raise ValueError("history_days must be at least 30")
        if not 1 <= self.financial_quarters <= 20:
            raise ValueError("financial_quarters must be between 1 and 20")
        if self.announcement_days < 1:
            raise ValueError("announcement_days must be positive")


def _is_security_code(value: str) -> bool:
    if len(value) != 9 or value[6] != ".":
        return False
    return value[:6].isdigit() and value[7:] in {"SH", "SZ"}


def to_baostock_code(security_code: str) -> str:
    if not _is_security_code(security_code):
        raise ValueError("security_code must look like 600000.SH or 000001.SZ")
    return f"{security_code[7:].lower()}.{security_code[:6]}"


def _evidence_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode()).hexdigest()[:10].upper()
    return f"{prefix}-{digest}"


def _quarters(as_of_date: date, count: int) -> list[tuple[int, int]]:
    quarter = (as_of_date.month - 1) // 3 + 1
    year = as_of_date.year
    result: list[tuple[int, int]] = []
    for _ in range(count + 2):
        result.append((year, quarter))
        quarter -= 1
        if quarter == 0:
            year -= 1
            quarter = 4
    return result


def _float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _latest_published(frame: pd.DataFrame, as_of_date: date) -> pd.Series | None:
    if frame.empty or "pubDate" not in frame.columns:
        return None
    values = frame.copy()
    values["pubDate"] = pd.to_datetime(values["pubDate"], errors="coerce")
    values = values.loc[values["pubDate"].dt.date <= as_of_date]
    values = values.dropna(subset=["pubDate"]).sort_values("pubDate")
    return None if values.empty else values.iloc[-1]


class CNInfoAnnouncementClient:
    """Small client for the public announcement search used by CNInfo's website."""

    endpoint = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
    security_search_endpoint = (
        "https://www.cninfo.com.cn/new/information/topSearch/query"
    )
    static_base = "https://static.cninfo.com.cn/"

    def __init__(
        self,
        *,
        session: HTTPSession | None = None,
        timeout_seconds: float = 20.0,
        page_size: int = 30,
        max_pages: int = 10,
    ) -> None:
        if not 1 <= page_size <= 50:
            raise ValueError("page_size must be between 1 and 50")
        if not 1 <= max_pages <= 100:
            raise ValueError("max_pages must be between 1 and 100")
        self.session = session or cast(HTTPSession, requests.Session())
        self.timeout_seconds = timeout_seconds
        self.page_size = page_size
        self.max_pages = max_pages
        self.session.headers.update(
            {
                "User-Agent": "QuantResearchAgent/0.1 public-disclosure research",
                "Referer": "https://www.cninfo.com.cn/",
            }
        )

    def search(
        self,
        security_code: str,
        *,
        start_date: date,
        end_date: date,
        category: str = "",
    ) -> list[EvidenceRecord]:
        if start_date > end_date:
            raise ValueError("announcement start_date must not exceed end_date")
        exchange = security_code.split(".")[-1]
        code = security_code[:6]
        try:
            security_response = self.session.post(
                self.security_search_endpoint,
                data={"keyWord": code, "maxNum": 10},
                timeout=self.timeout_seconds,
            )
            security_response.raise_for_status()
            candidates = security_response.json()
            match = next(
                item
                for item in candidates
                if str(item.get("code") or "") == code and str(item.get("orgId") or "")
            )
            stock_filter = f"{code},{match['orgId']}"
        except (requests.RequestException, ValueError, TypeError, StopIteration) as exc:
            raise CompanyPublicDataError(
                f"CNInfo could not resolve security {security_code}"
            ) from exc
        payload = {
            "pageNum": 1,
            "pageSize": self.page_size,
            "column": "sse" if exchange == "SH" else "szse",
            "tabName": "fulltext",
            "plate": "",
            "stock": stock_filter,
            "searchkey": "",
            "secid": "",
            "category": category,
            "trade": "",
            "seDate": f"{start_date.isoformat()}~{end_date.isoformat()}",
            "sortName": "",
            "sortType": "",
            "isHLtitle": "true",
        }
        records: list[EvidenceRecord] = []
        retrieved = datetime.now(UTC)
        seen: set[str] = set()
        for page_number in range(1, self.max_pages + 1):
            payload["pageNum"] = page_number
            try:
                response = self.session.post(
                    self.endpoint,
                    data=payload,
                    timeout=self.timeout_seconds,
                )
                response.raise_for_status()
                data = response.json()
            except (requests.RequestException, ValueError, TypeError) as exc:
                raise CompanyPublicDataError(
                    "CNInfo announcement request failed"
                ) from exc
            announcements = data.get("announcements") or []
            for item in announcements:
                title = (
                    str(item.get("announcementTitle") or "")
                    .replace("<em>", "")
                    .replace("</em>", "")
                    .strip()
                )
                adjunct = str(item.get("adjunctUrl") or "").lstrip("/")
                timestamp = item.get("announcementTime")
                try:
                    published = datetime.fromtimestamp(float(timestamp) / 1000, tz=UTC)
                except (TypeError, ValueError, OSError):
                    continue
                if not title or not adjunct or published.date() > end_date:
                    continue
                announcement_id = str(item.get("announcementId") or adjunct)
                evidence_id = _evidence_id("CNINFO", security_code, announcement_id)
                if evidence_id in seen:
                    continue
                seen.add(evidence_id)
                records.append(
                    EvidenceRecord(
                        evidence_id=evidence_id,
                        source_type="company_announcement",
                        title=title,
                        source_name="CNInfo",
                        url=self.static_base + adjunct,
                        document_id=announcement_id,
                        published_at=published,
                        retrieved_at=retrieved,
                        summary="Official disclosure title; full document interpretation is pending.",
                    )
                )
            total = int(data.get("totalAnnouncement") or len(announcements))
            if (
                not announcements
                or len(seen) >= total
                or len(announcements) < self.page_size
            ):
                break
        return records

    def search_annual_reports(
        self,
        security_code: str,
        *,
        start_date: date,
        end_date: date,
    ) -> list[EvidenceRecord]:
        return self.search(
            security_code,
            start_date=start_date,
            end_date=end_date,
            category="category_ndbg_szsh;",
        )


class BaoStockCompanyDataProvider:
    """Build a point-in-time market and financial snapshot without an API key."""

    statement_queries: ClassVar[dict[str, str]] = {
        "profit": "query_profit_data",
        "balance": "query_balance_data",
        "cash_flow": "query_cash_flow_data",
        "growth": "query_growth_data",
    }

    def __init__(
        self,
        *,
        api: CompanyBaoStockAPI | None = None,
        announcement_client: CNInfoAnnouncementClient | None = None,
    ) -> None:
        self.api = api or cast(CompanyBaoStockAPI, bs)
        self.announcement_client = announcement_client

    def _query(self, result: BaoStockResult, endpoint: str) -> pd.DataFrame:
        try:
            return _result_frame(result, endpoint)
        except BaoStockDataError as exc:
            raise CompanyPublicDataError(str(exc)) from exc

    def build(self, config: CompanyPublicDataConfig) -> CompanyPublicDataPackage:
        provider_code = to_baostock_code(config.security_code)
        login = self.api.login()
        if login.error_code != "0":
            raise CompanyPublicDataError(
                f"BaoStock login failed [{login.error_code}]: {login.error_msg}"
            )
        try:
            history = self._query(
                self.api.query_history_k_data_plus(
                    provider_code,
                    "date,code,close,pctChg,turn,amount,peTTM,pbMRQ,psTTM,pcfNcfTTM,tradestatus",
                    start_date=(
                        config.as_of_date - timedelta(days=config.history_days)
                    ).isoformat(),
                    end_date=config.as_of_date.isoformat(),
                    frequency="d",
                    adjustflag="3",
                ),
                "query_history_k_data_plus",
            )
            statements: dict[str, pd.DataFrame] = {}
            for name, query_name in self.statement_queries.items():
                frames = []
                query = getattr(self.api, query_name)
                for year, quarter in _quarters(
                    config.as_of_date, config.financial_quarters
                ):
                    frame = self._query(
                        query(code=provider_code, year=year, quarter=quarter),
                        query_name,
                    )
                    if not frame.empty:
                        frames.append(frame)
                statements[name] = (
                    pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
                )
        finally:
            self.api.logout()

        package = self._assemble(config, provider_code, history, statements)
        if self.announcement_client is None:
            return package
        try:
            announcements = self.announcement_client.search(
                config.security_code,
                start_date=config.as_of_date - timedelta(days=config.announcement_days),
                end_date=config.as_of_date,
            )
        except CompanyPublicDataError as exc:
            return CompanyPublicDataPackage.model_validate(
                {
                    **package.model_dump(mode="python"),
                    "warnings": [*package.warnings, str(exc)],
                }
            )
        return CompanyPublicDataPackage.model_validate(
            {
                **package.model_dump(mode="python"),
                "evidence": [*package.evidence, *announcements],
            }
        )

    @staticmethod
    def _assemble(
        config: CompanyPublicDataConfig,
        provider_code: str,
        history: pd.DataFrame,
        statements: dict[str, pd.DataFrame],
    ) -> CompanyPublicDataPackage:
        if history.empty:
            raise CompanyPublicDataError("BaoStock returned no market history")
        daily = history.copy()
        daily["date"] = pd.to_datetime(daily["date"], errors="coerce")
        daily = daily.loc[daily["tradestatus"].astype(str) == "1"]
        daily = daily.dropna(subset=["date"]).sort_values("date")
        daily = daily.loc[daily["date"].dt.date <= config.as_of_date]
        if daily.empty:
            raise CompanyPublicDataError(
                "BaoStock returned no valid pre-cutoff history"
            )
        latest = daily.iloc[-1]
        observed = latest["date"].date()
        market_evidence_id = _evidence_id(
            "BAOSTOCK-MKT", config.security_code, observed.isoformat()
        )
        retrieved = datetime.now(UTC)
        evidence = [
            EvidenceRecord(
                evidence_id=market_evidence_id,
                source_type="market_data",
                title=f"{config.company_name} BaoStock market snapshot",
                source_name="BaoStock",
                document_id=f"baostock:{provider_code}:{observed.isoformat()}",
                published_at=datetime.combine(
                    observed, datetime.min.time(), tzinfo=UTC
                ),
                retrieved_at=retrieved,
                summary="Unadjusted daily market history through the stated cutoff.",
            )
        ]
        closes = pd.to_numeric(daily["close"], errors="coerce").dropna()
        returns = pd.to_numeric(daily["pctChg"], errors="coerce").dropna() / 100
        market_values: dict[str, tuple[float | None, str]] = {
            "close": (_float(latest.get("close")), "CNY/share"),
            "pe_ttm": (_float(latest.get("peTTM")), "x"),
            "pb_mrq": (_float(latest.get("pbMRQ")), "x"),
            "ps_ttm": (_float(latest.get("psTTM")), "x"),
            "pcf_ncf_ttm": (_float(latest.get("pcfNcfTTM")), "x"),
            "one_year_return": (
                float(closes.iloc[-1] / closes.iloc[0] - 1)
                if len(closes) >= 2 and closes.iloc[0] != 0
                else None,
                "ratio",
            ),
            "annualized_volatility": (
                float(returns.std(ddof=1) * math.sqrt(252))
                if len(returns) >= 2
                else None,
                "ratio",
            ),
            "max_drawdown": (
                float((closes / closes.cummax() - 1).min())
                if not closes.empty
                else None,
                "ratio",
            ),
            "average_turnover": (
                _float(pd.to_numeric(daily["turn"], errors="coerce").mean()),
                "percent",
            ),
        }
        market_metrics = [
            ObservedMetric(
                name=name,
                value=value,
                unit=unit,
                observation_date=observed,
                source_evidence_id=market_evidence_id,
            )
            for name, (value, unit) in market_values.items()
            if value is not None
        ]

        financial_metrics: list[ObservedMetric] = []
        warnings: list[str] = []
        for statement_name, frame in statements.items():
            row = _latest_published(frame, config.as_of_date)
            if row is None:
                warnings.append(
                    f"BaoStock returned no published {statement_name} statement before cutoff."
                )
                continue
            publication = cast(pd.Timestamp, row["pubDate"]).date()
            period = str(row.get("statDate") or publication.isoformat())
            evidence_id = _evidence_id(
                f"BAOSTOCK-{statement_name.upper()}",
                config.security_code,
                period,
                publication.isoformat(),
            )
            evidence.append(
                EvidenceRecord(
                    evidence_id=evidence_id,
                    source_type=f"financial_{statement_name}",
                    title=f"{config.company_name} {statement_name} indicators for {period}",
                    source_name="BaoStock",
                    document_id=f"baostock:{provider_code}:{statement_name}:{period}",
                    published_at=datetime.combine(
                        publication, datetime.min.time(), tzinfo=UTC
                    ),
                    retrieved_at=retrieved,
                    summary="Provider financial indicators selected only after publication date.",
                )
            )
            for name, raw_value in row.items():
                if name in {"code", "pubDate", "statDate"}:
                    continue
                value = _float(raw_value)
                if value is None:
                    continue
                financial_metrics.append(
                    ObservedMetric(
                        name=f"{statement_name}.{name}",
                        value=value,
                        unit="provider_reported",
                        observation_date=publication,
                        source_evidence_id=evidence_id,
                    )
                )
        return CompanyPublicDataPackage(
            company_name=config.company_name,
            security_code=config.security_code,
            provider_code=provider_code,
            as_of_date=config.as_of_date,
            market_metrics=market_metrics,
            financial_metrics=financial_metrics,
            evidence=evidence,
            warnings=warnings,
            look_ahead_bias_checked=True,
        )
