from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

import data_sources.baostock_returns as returns_module
from data_sources.baostock_returns import (
    BaoStockReturnConfig,
    BaoStockReturnDataError,
    _fetch_one,
    _login,
    _normalize_history,
    _paged_frame,
    align_baostock_future_returns,
    build_baostock_return_cache,
    load_baostock_monthly_returns,
    stock_cache_path,
)


class FakeResult:
    def __init__(self) -> None:
        self.error_code = "0"
        self.error_msg = "success"
        self.fields = ["date", "code", "close", "pctChg"]
        self.data = [["2020-01-31", "sz.000001", "10", "2.5"]]
        self.cur_row_num = 0

    def next(self) -> bool:
        return False


def _config(tmp_path: Path, **overrides) -> BaoStockReturnConfig:
    values = {
        "codes": ("sz.000001",),
        "start_date": date(2020, 1, 1),
        "end_date": date(2020, 3, 31),
        "output_directory": tmp_path,
        **overrides,
    }
    return BaoStockReturnConfig(**values)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"codes": ()}, "At least one"),
        ({"end_date": date(2020, 1, 1)}, "earlier"),
        ({"workers": 9}, "workers"),
        ({"adjust_flag": "9"}, "adjust_flag"),
        ({"workers": 4, "batch_size": 2}, "batch_size"),
        ({"batch_pause_seconds": -1}, "nonnegative"),
    ],
)
def test_config_validation(tmp_path: Path, overrides: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        _config(tmp_path, **overrides)


def test_paged_frame_and_error() -> None:
    frame = _paged_frame(FakeResult())
    assert frame["pctChg"].item() == "2.5"
    failed = FakeResult()
    failed.error_code = "1"
    failed.error_msg = "bad"
    with pytest.raises(BaoStockReturnDataError, match="bad"):
        _paged_frame(failed)


def test_paged_frame_empty_result() -> None:
    result = FakeResult()
    result.data = []
    frame = _paged_frame(result)
    assert frame.empty
    assert frame.columns.tolist() == result.fields


def test_normalize_monthly_and_daily_history() -> None:
    monthly = _normalize_history(_paged_frame(FakeResult()), "sz.000001", "m")
    assert monthly["daily_return"].item() == 0.025
    assert monthly["trade_status"].item() == "1"
    daily_source = pd.DataFrame(
        {
            "date": ["2020-01-02"],
            "code": ["sz.000001"],
            "close": ["10"],
            "preclose": ["9.9"],
            "pctChg": ["1.01"],
            "tradestatus": ["1"],
            "isST": ["0"],
        }
    )
    daily = _normalize_history(daily_source, "sz.000001", "d")
    assert daily["preclose"].item() == 9.9
    assert not daily["special_treatment"].item()


def test_normalize_rejects_missing_fields_and_duplicate_dates() -> None:
    with pytest.raises(BaoStockReturnDataError, match="missing"):
        _normalize_history(pd.DataFrame({"date": ["2020-01-01"]}), "sz.1", "m")

    duplicate = pd.DataFrame(
        {
            "date": ["2020-01-31", "2020-01-31"],
            "code": ["sz.1", "sz.1"],
            "close": ["10", "10"],
            "pctChg": ["1", "1"],
        }
    )
    with pytest.raises(BaoStockReturnDataError, match="duplicate dates"):
        _normalize_history(duplicate, "sz.1", "m")


def test_login_retries_and_raises(monkeypatch) -> None:
    monkeypatch.setattr(
        returns_module.bs,
        "login",
        lambda: SimpleNamespace(error_code="1", error_msg="offline"),
    )
    monkeypatch.setattr(returns_module.time, "sleep", lambda _seconds: None)
    with pytest.raises(BaoStockReturnDataError, match="offline"):
        _login()


def test_login_sets_socket_timeout_and_registers_logout(monkeypatch) -> None:
    socket = SimpleNamespace(timeout=None)
    socket.settimeout = lambda value: setattr(socket, "timeout", value)
    registered: list[object] = []
    monkeypatch.setattr(
        returns_module.bs,
        "login",
        lambda: SimpleNamespace(error_code="0", error_msg="success"),
    )
    monkeypatch.setattr(returns_module.context, "default_socket", socket, raising=False)
    monkeypatch.setattr(returns_module.atexit, "register", registered.append)
    _login()
    assert socket.timeout == 45
    assert registered == [returns_module.bs.logout]


def test_fetch_one_writes_cache(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        returns_module.bs,
        "query_history_k_data_plus",
        lambda *args, **kwargs: FakeResult(),
    )
    result = _fetch_one(
        ("sz.000001", "2020-01-01", "2020-03-31", "3", "m", str(tmp_path))
    )
    assert result["rows"] == 1
    assert stock_cache_path(tmp_path, "sz.000001").exists()


def test_load_and_align_monthly_returns(tmp_path: Path) -> None:
    stock_directory = tmp_path / "stocks"
    stock_directory.mkdir()
    pd.DataFrame(
        {
            "date": pd.to_datetime(["2020-02-28", "2020-03-31"]),
            "stock_id": ["sz.000001", "sz.000001"],
            "daily_return": [0.02, -0.03],
        }
    ).to_parquet(stock_directory / "sz_000001.parquet", index=False)
    monthly = load_baostock_monthly_returns(stock_directory)
    panel = pd.DataFrame(
        {
            "stock_id": ["000001"],
            "month": [pd.Period("2020-01", freq="M")],
            "date": [pd.Timestamp("2020-01-31")],
            "target_date": [pd.Timestamp("2020-02-28")],
            "target_month": [pd.Period("2020-02", freq="M")],
            "future_return": [0.021],
        }
    )
    aligned, audit = align_baostock_future_returns(panel, monthly)
    assert aligned["future_return"].item() == 0.02
    assert aligned["future_return_akshare"].item() == 0.021
    assert audit["baostock_target_matches"] == 1


def test_load_monthly_returns_rejects_empty_and_duplicate_cache(tmp_path: Path) -> None:
    with pytest.raises(BaoStockReturnDataError, match="No BaoStock"):
        load_baostock_monthly_returns(tmp_path)

    duplicate = pd.DataFrame(
        {
            "date": pd.to_datetime(["2020-02-28", "2020-02-28"]),
            "stock_id": ["sz.000001", "sz.000001"],
            "daily_return": [0.01, 0.02],
        }
    )
    duplicate.to_parquet(tmp_path / "duplicate.parquet", index=False)
    with pytest.raises(BaoStockReturnDataError, match="duplicate stock-month"):
        load_baostock_monthly_returns(tmp_path)


def test_cache_hit_build_writes_complete_manifest(tmp_path: Path) -> None:
    stock_directory = tmp_path / "stocks"
    stock_directory.mkdir()
    pd.DataFrame({"date": pd.to_datetime(["2020-01-31"])}).to_parquet(
        stock_cache_path(stock_directory, "sz.000001"), index=False
    )
    result = build_baostock_return_cache(_config(tmp_path))
    assert result.completed_codes == 1
    assert result.cache_hits == 1
    assert result.manifest_path.exists()
