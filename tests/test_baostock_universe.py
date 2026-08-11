import json
from datetime import date

import pandas as pd

from config import BaoStockSettings
from data_sources.baostock import _result_frame
from data_sources.baostock_universe import (
    BaoStockHistoricalUniverseBuilder,
    BaoStockUniverseConfig,
)


class FakeResult:
    def __init__(self, frame: pd.DataFrame) -> None:
        self.frame = frame
        self.error_code = "0"
        self.error_msg = "success"
        self.fields = list(frame.columns)

    def get_data(self) -> pd.DataFrame:
        return self.frame.copy()


class FakeUniverseAPI:
    def login(self) -> FakeResult:
        return FakeResult(pd.DataFrame())

    def logout(self) -> FakeResult:
        return FakeResult(pd.DataFrame())

    def query_trade_dates(self, **kwargs) -> FakeResult:
        return FakeResult(
            pd.DataFrame(
                {
                    "calendar_date": [
                        "2024-01-30",
                        "2024-01-31",
                        "2024-02-28",
                        "2024-02-29",
                    ],
                    "is_trading_day": ["1", "1", "1", "1"],
                }
            )
        )

    def query_all_stock(self, **kwargs) -> FakeResult:
        return FakeResult(
            pd.DataFrame(
                {
                    "code": ["sh.600000", "sz.000001", "bj.430001", "sh.000001"],
                    "tradeStatus": ["1", "1", "0", "1"],
                    "code_name": ["浦发银行", "平安银行", "ST测试", "上证指数"],
                }
            )
        )


def test_historical_universe_builds_month_end_snapshots_and_cache(tmp_path) -> None:
    builder = BaoStockHistoricalUniverseBuilder(
        BaoStockSettings(cache_directory=tmp_path), api=FakeUniverseAPI()
    )
    config = BaoStockUniverseConfig(
        start_date=date(2024, 1, 1), end_date=date(2024, 2, 29)
    )

    first = builder.build(config)
    universe = pd.read_parquet(first.universe_path)
    second = builder.build(config)
    manifest = json.loads(first.manifest_path.read_text(encoding="utf-8"))

    assert first.cache_hit is False
    assert second.cache_hit is True
    assert first.monthly_snapshots == 2
    assert first.unique_securities == 3
    assert manifest["observed_exchanges"] == ["bj", "sh", "sz"]
    assert "sh.000001" not in set(universe["stock_id"])
    assert universe.loc[universe["stock_id"] == "bj.430001", "special_treatment"].all()


def test_result_frame_uses_cursor_without_losing_initial_batch() -> None:
    class CursorResult:
        error_code = "0"
        error_msg = "success"

        def __init__(self) -> None:
            self.fields = ["code"]
            self.rows = [["sh.600000"], ["sh.688001"], ["sz.000001"]]
            self.position = -1

        def get_data(self):
            raise AssertionError("legacy get_data must not be called")

        def next(self) -> bool:
            self.position += 1
            return self.position < len(self.rows)

        def get_row_data(self) -> list[str]:
            return self.rows[self.position]

    frame = _result_frame(CursorResult(), "fixture")

    assert frame["code"].tolist() == ["sh.600000", "sh.688001", "sz.000001"]
