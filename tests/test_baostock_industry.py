from datetime import date
from pathlib import Path

import pandas as pd
import pytest

import data_sources.baostock_industry as industry_module
from data_sources.baostock_industry import (
    BaoStockIndustryConfig,
    BaoStockIndustryError,
    _normalize_industry_snapshot,
    _repair_baostock_text,
    align_industry_to_panel,
    build_baostock_industry_cache,
    industry_snapshot_path,
    load_industry_snapshots,
)


class FakeResult:
    def __init__(self) -> None:
        self.error_code = "0"
        self.error_msg = "success"
        self.fields = [
            "updateDate",
            "code",
            "code_name",
            "industry",
            "industryClassification",
        ]
        self.data = [
            ["2020-01-20", "sh.600000", "A", "J66货币金融服务", "证监会行业分类"]
        ]
        self.cur_row_num = 0

    def next(self) -> bool:
        return False


def _source() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "updateDate": ["2010-01-25", "2010-01-25", "2010-01-25"],
            "code": ["sh.600000", "sh.600001", "sh.600002"],
            "code_name": ["银行", "地产", "制造"],
            "industry": ["金融保险业-银行业", "K70房地产业", "C39计算机制造业"],
            "industryClassification": ["证监会行业分类"] * 3,
        }
    )


def test_config_validation(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="At least one"):
        BaoStockIndustryConfig(snapshot_dates=(), output_directory=tmp_path)
    with pytest.raises(ValueError, match="nonnegative"):
        BaoStockIndustryConfig(
            snapshot_dates=(date(2020, 1, 28),),
            output_directory=tmp_path,
            pause_seconds=-1,
        )


def test_normalize_industry_flags_finance_and_real_estate() -> None:
    frame = _normalize_industry_snapshot(_source(), date(2010, 1, 28))
    assert frame["financial_industry"].tolist() == [True, False, False]
    assert frame["real_estate_industry"].tolist() == [False, True, False]
    assert frame["excluded_industry"].tolist() == [True, True, False]
    assert _repair_baostock_text("ÖÆÔìÒµ") == "制造业"


def test_normalize_rejects_bad_contract() -> None:
    with pytest.raises(BaoStockIndustryError, match="missing"):
        _normalize_industry_snapshot(pd.DataFrame({"code": ["x"]}), date(2020, 1, 1))
    future = _source().assign(updateDate="2020-02-01")
    with pytest.raises(BaoStockIndustryError, match="after snapshot"):
        _normalize_industry_snapshot(future, date(2020, 1, 1))


def test_build_download_and_cache_hit(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(industry_module, "_login", lambda: None)
    monkeypatch.setattr(industry_module.bs, "logout", lambda: None)
    monkeypatch.setattr(
        industry_module.bs, "query_stock_industry", lambda **_kwargs: FakeResult()
    )
    config = BaoStockIndustryConfig(
        snapshot_dates=(date(2020, 1, 28),),
        output_directory=tmp_path,
        pause_seconds=0,
    )
    result = build_baostock_industry_cache(config)
    assert result.completed_snapshots == 1
    assert result.rows == 1
    cached = build_baostock_industry_cache(config)
    assert cached.cache_hits == 1


def test_load_and_backward_align_snapshots(tmp_path: Path) -> None:
    directory = tmp_path / "snapshots"
    directory.mkdir()
    snapshot = _normalize_industry_snapshot(_source(), date(2010, 1, 28))
    snapshot.to_parquet(
        industry_snapshot_path(directory, date(2010, 1, 28)), index=False
    )
    loaded = load_industry_snapshots(directory)
    panel = pd.DataFrame(
        {
            "stock_id": ["600000", "600002"],
            "date": pd.to_datetime(["2010-02-26", "2010-02-26"]),
            "value": [1, 2],
        }
    )
    aligned = align_industry_to_panel(panel, loaded)
    assert aligned["industry"].tolist() == ["金融保险业-银行业", "C39计算机制造业"]


def test_load_rejects_missing_directory(tmp_path: Path) -> None:
    with pytest.raises(BaoStockIndustryError, match="No industry"):
        load_industry_snapshots(tmp_path)
