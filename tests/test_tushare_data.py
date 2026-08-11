from datetime import date

import numpy as np
import pandas as pd
import pytest

from config import ConfigurationError, TushareSettings
from data_sources.tushare import TushareBuildConfig, TushareIVOLDataBuilder


class FakeTushareAPI:
    def __init__(self) -> None:
        dates = pd.bdate_range("2023-01-02", "2024-05-31")
        self.daily_frames = {}
        self.basic_frames = {}
        for stock_number, code in enumerate(("000001.SZ", "600000.SH"), start=1):
            sequence = np.arange(len(dates), dtype=float)
            returns = (
                0.08 * np.sin(sequence / (4.0 + stock_number))
                + 0.03 * np.cos(sequence / 9.0)
                + stock_number * 0.002
            )
            formatted_dates = dates.strftime("%Y%m%d")
            self.daily_frames[code] = pd.DataFrame(
                {
                    "ts_code": code,
                    "trade_date": formatted_dates,
                    "close": 10.0 + sequence / 100,
                    "pre_close": 10.0 + (sequence - 1) / 100,
                    "pct_chg": returns,
                    "vol": 1000.0 + sequence,
                    "amount": 5000.0 + sequence,
                }
            )
            self.basic_frames[code] = pd.DataFrame(
                {
                    "ts_code": code,
                    "trade_date": formatted_dates,
                    "total_mv": 100_000.0 + stock_number * 1000 + sequence,
                    "pb": 1.5 + stock_number * 0.1,
                    "turnover_rate": 1.0,
                }
            )

    def daily(self, **kwargs):
        return self.daily_frames[kwargs["ts_code"]].copy()

    def daily_basic(self, **kwargs):
        return self.basic_frames[kwargs["ts_code"]].copy()


def _build_config() -> TushareBuildConfig:
    return TushareBuildConfig(
        ts_codes=("000001.SZ", "600000.SH"),
        start_date=date(2023, 1, 1),
        end_date=date(2024, 5, 31),
    )


def test_tushare_settings_require_token(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("TUSHARE_TOKEN", raising=False)
    with pytest.raises(ConfigurationError, match="TUSHARE_TOKEN"):
        TushareSettings.from_env(tmp_path / "missing.env")


def test_tushare_build_config_requires_exchange_suffix() -> None:
    with pytest.raises(ValueError, match="exchange suffix"):
        TushareBuildConfig(
            ts_codes=("000001",),
            start_date=date(2023, 1, 1),
            end_date=date(2024, 5, 31),
        )


def test_tushare_builder_prepares_and_caches_ivol_panel(tmp_path) -> None:
    builder = TushareIVOLDataBuilder(
        TushareSettings(token="offline-token", cache_directory=tmp_path),
        api=FakeTushareAPI(),
    )

    first = builder.build(_build_config())
    panel = pd.read_parquet(first.panel_path)
    second = builder.build(_build_config())

    assert first.cache_hit is False
    assert first.raw_rows > first.panel_rows > 0
    assert second.cache_hit is True
    assert set(
        [
            "stock_id",
            "date",
            "target_date",
            "future_return",
            "IVOL",
            "size",
            "bm",
            "momentum",
        ]
    ).issubset(panel.columns)
    assert (panel["target_date"] > panel["date"]).all()
    assert panel["IVOL"].gt(0).all()
