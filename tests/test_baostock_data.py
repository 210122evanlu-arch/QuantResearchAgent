from datetime import date

import numpy as np
import pandas as pd
import pytest

from config import BaoStockSettings
from data_sources.baostock import BaoStockBuildConfig, BaoStockIVOLDataBuilder


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


class FakeBaoStockAPI:
    def __init__(self) -> None:
        self.logged_out = False
        self.history_frames: dict[str, pd.DataFrame] = {}
        dates = pd.bdate_range("2023-01-02", "2024-05-31")
        for stock_number, code in enumerate(("sz.000001", "sh.600000"), start=1):
            sequence = np.arange(len(dates), dtype=float)
            returns = (
                0.08 * np.sin(sequence / (4.0 + stock_number))
                + 0.03 * np.cos(sequence / 9.0)
                + stock_number * 0.002
            )
            self.history_frames[code] = pd.DataFrame(
                {
                    "date": dates.strftime("%Y-%m-%d"),
                    "code": code,
                    "open": 10.0,
                    "high": 10.2,
                    "low": 9.8,
                    "close": 10.0 + sequence / 100,
                    "preclose": 10.0 + (sequence - 1) / 100,
                    "volume": 1000.0 + sequence,
                    "amount": 5000.0 + sequence,
                    "adjustflag": "2",
                    "turn": "1.0",
                    "tradestatus": "1",
                    "pctChg": returns,
                    "peTTM": "10",
                    "pbMRQ": str(1.5 + stock_number * 0.1),
                    "psTTM": "2",
                    "pcfNcfTTM": "8",
                    "isST": "0",
                }
            )

    def login(self) -> FakeResult:
        return FakeResult()

    def logout(self) -> FakeResult:
        self.logged_out = True
        return FakeResult()

    def query_history_k_data_plus(self, code, fields, **kwargs) -> FakeResult:
        return FakeResult(self.history_frames[code])

    def query_profit_data(self, *, code, year, quarter) -> FakeResult:
        if year not in {2022, 2023, 2024}:
            return FakeResult()
        month = quarter * 3
        publication = pd.Timestamp(year=year, month=month, day=1) + pd.offsets.MonthEnd(
            1
        )
        publication += pd.Timedelta(days=30)
        return FakeResult(
            pd.DataFrame(
                {
                    "code": [code],
                    "pubDate": [publication.strftime("%Y-%m-%d")],
                    "statDate": [pd.Timestamp(year, month, 1).strftime("%Y-%m-%d")],
                    "totalShare": [1_000_000.0],
                    "liqaShare": [800_000.0],
                }
            )
        )


def _config() -> BaoStockBuildConfig:
    return BaoStockBuildConfig(
        codes=("sz.000001", "sh.600000"),
        start_date=date(2023, 1, 1),
        end_date=date(2024, 5, 31),
    )


def test_baostock_is_keyless_and_uses_safe_defaults(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("BAOSTOCK_CACHE_DIR", str(tmp_path))
    monkeypatch.delenv("BAOSTOCK_ADJUST_FLAG", raising=False)

    settings = BaoStockSettings.from_env(tmp_path / "missing.env")

    assert settings.cache_directory == tmp_path
    assert settings.adjust_flag == "2"


def test_baostock_config_rejects_non_provider_codes() -> None:
    with pytest.raises(ValueError, match=r"sh\.600000"):
        BaoStockBuildConfig(
            codes=("600000.SH",),
            start_date=date(2023, 1, 1),
            end_date=date(2024, 5, 31),
        )


def test_baostock_builder_prepares_and_caches_ivol_panel(tmp_path) -> None:
    api = FakeBaoStockAPI()
    builder = BaoStockIVOLDataBuilder(
        BaoStockSettings(cache_directory=tmp_path), api=api
    )

    first = builder.build(_config())
    panel = pd.read_parquet(first.panel_path)
    raw = pd.read_parquet(first.raw_path)
    second = builder.build(_config())

    assert first.cache_hit is False
    assert second.cache_hit is True
    assert first.raw_rows > first.panel_rows > 0
    assert api.logged_out is True
    assert (pd.to_datetime(raw["pubDate"]) <= pd.to_datetime(raw["trade_date"])).all()
    assert {
        "stock_id",
        "date",
        "target_date",
        "future_return",
        "IVOL",
        "size",
        "bm",
        "momentum",
    }.issubset(panel.columns)
    assert panel["IVOL"].gt(0).all()
