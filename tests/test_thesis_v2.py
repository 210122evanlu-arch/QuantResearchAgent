from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import data_sources.thesis_v2 as thesis_v2
from data_sources.thesis_v2 import (
    ThesisV2Config,
    _estimate_stock_months,
    assemble_thesis_v2_panel,
    build_return_ivol_panel,
    build_thesis_v2_dataset,
    is_p9709_stock,
    load_monthly_book_to_market,
    load_monthly_market_cap,
    load_monthly_turnover,
    load_monthly_universe,
    normalize_stock_code,
    save_thesis_v2_dataset,
)


def _config() -> ThesisV2Config:
    return ThesisV2Config(
        daily_directory=Path("daily"),
        factor_path=Path("factor.parquet"),
        market_cap_paths=(Path("cap.csv"),),
        pb_paths=(Path("pb.csv"),),
        turnover_path=Path("turnover.xlsx"),
        exclude_recent_listings_days=0,
    )


def test_code_normalization_and_p9709_scope() -> None:
    assert normalize_stock_code("sh.600000") == "600000"
    assert normalize_stock_code(1) == "000001"
    assert is_p9709_stock("000001")
    assert is_p9709_stock("300001")
    assert not is_p9709_stock("688001")
    assert not is_p9709_stock("920992")


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"minimum_daily_observations": 7}, "at least 8"),
        ({"residual_ddof": 2}, "0 or 1"),
        ({"exclude_recent_listings_days": -1}, "nonnegative"),
        ({"risk_free_max_staleness_days": -1}, "nonnegative"),
        ({"main_board_daily_return_limit": 0}, "main_board"),
        ({"growth_board_daily_return_limit": 1}, "growth_board"),
    ],
)
def test_config_validation(overrides: dict, message: str) -> None:
    values = {
        "daily_directory": Path("daily"),
        "factor_path": Path("factor.parquet"),
        "market_cap_paths": (Path("cap.csv"),),
        "pb_paths": (Path("pb.csv"),),
        "turnover_path": Path("turnover.xlsx"),
        **overrides,
    }
    with pytest.raises(ValueError, match=message):
        ThesisV2Config(**values)


def _synthetic_sources(tmp_path: Path) -> tuple[ThesisV2Config, pd.DataFrame]:
    dates = pd.bdate_range("2020-01-01", "2020-04-30")
    rng = np.random.default_rng(42)
    factors = pd.DataFrame(
        {
            "date": dates,
            "MKT": rng.normal(0, 0.01, len(dates)),
            "SMB": rng.normal(0, 0.01, len(dates)),
            "HML": rng.normal(0, 0.01, len(dates)),
            "RMW": rng.normal(0, 0.01, len(dates)),
            "CMA": rng.normal(0, 0.01, len(dates)),
        }
    )
    factor_path = tmp_path / "factors.parquet"
    factors.to_parquet(factor_path, index=False)
    daily_directory = tmp_path / "daily"
    daily_directory.mkdir()
    returns = 0.001 + 0.2 * factors["MKT"] + rng.normal(0, 0.005, len(dates))
    close = 10 * (1 + returns).cumprod()
    pd.DataFrame({"date": dates, "open": close, "high": close, "close": close}).to_csv(
        daily_directory / "000001.csv", index=False
    )
    config = ThesisV2Config(
        daily_directory=daily_directory,
        factor_path=factor_path,
        market_cap_paths=(),
        pb_paths=(),
        turnover_path=tmp_path / "turnover.xlsx",
        cache_directory=tmp_path / "cache",
        start_date="2020-01-01",
        end_date="2020-04-30",
        exclude_recent_listings_days=0,
    )
    return config, factors


def test_daily_return_ivol_builder_and_cache(tmp_path: Path) -> None:
    config, factors = _synthetic_sources(tmp_path)
    rows = _estimate_stock_months(
        config.daily_directory / "000001.csv", factors, config
    )
    assert len(rows) == 4
    assert all(row["IVOL"] > 0 for row in rows)
    assert (
        _estimate_stock_months(config.daily_directory / "688001.csv", factors, config)
        == []
    )

    panel = build_return_ivol_panel(config)
    assert panel["future_return"].notna().sum() == 3
    assert panel.loc[
        panel["future_return"].notna(), "target_is_next_calendar_month"
    ].all()
    cached = build_return_ivol_panel(config)
    pd.testing.assert_frame_equal(panel, cached)


def test_daily_return_ivol_uses_aligned_risk_free_proxy(tmp_path: Path) -> None:
    config, factors = _synthetic_sources(tmp_path)
    risk_free_path = tmp_path / "risk_free.parquet"
    pd.DataFrame(
        {
            "date": factors["date"],
            "RF": np.linspace(0.00001, 0.0002, len(factors)),
        }
    ).to_parquet(risk_free_path, index=False)
    rf_panel = build_return_ivol_panel(replace(config, risk_free_path=risk_free_path))
    assert rf_panel["monthly_rf"].gt(0).all()
    assert rf_panel.loc[rf_panel["future_return"].notna(), "future_rf"].gt(0).all()


def test_exchange_limit_violation_excludes_entire_month(tmp_path: Path) -> None:
    config, factors = _synthetic_sources(tmp_path)
    path = config.daily_directory / "000001.csv"
    daily = pd.read_csv(path)
    february = pd.to_datetime(daily["date"]).dt.month.eq(2)
    first = daily.index[february][5]
    daily.loc[first:, "close"] *= 1.2
    daily.to_csv(path, index=False)
    rows = _estimate_stock_months(path, factors, config)
    february_row = next(row for row in rows if str(row["month"]) == "2020-02")
    assert np.isnan(february_row["IVOL"])


def test_control_source_loaders(tmp_path: Path) -> None:
    cap_path = tmp_path / "cap.csv"
    pd.DataFrame(
        {
            "Stkcd": ["000001", "000001", "000001"],
            "Trddt": ["2020-01-02", "2020-01-31", "2020-02-28"],
            "Dsmvtll": [90, 100, 110],
        }
    ).to_csv(cap_path, index=False)
    cap = load_monthly_market_cap([cap_path])
    assert cap.loc[cap["month"].astype(str).eq("2020-01"), "market_cap"].item() == 100

    pb_path = tmp_path / "pb.csv"
    pd.DataFrame(
        {
            "Symbol": ["000001", "000001", "000002"],
            "TradingDate": ["2020-01-02", "2020-01-31", "2020-01-31"],
            "PB": [4, 2, -1],
        }
    ).to_csv(pb_path, index=False)
    bm = load_monthly_book_to_market([pb_path])
    assert bm["bm"].item() == 0.5

    turnover_path = tmp_path / "turnover.xlsx"
    turnover_source = pd.DataFrame(
        [
            ["证券代码", "交易月份", "月换手率", "总股换手率"],
            ["没有单位", "没有单位", "没有单位", "没有单位"],
            ["000001", "2020-01", 20.0, 18.0],
        ],
        columns=["Stkcd", "Trdmnt", "ToverOsM", "ToverTlM"],
    )
    turnover_source.to_excel(turnover_path, index=False)
    turnover = load_monthly_turnover(turnover_path)
    assert turnover["turnover"].item() == 20


def test_universe_loader_and_filtered_assembly(tmp_path: Path) -> None:
    universe_path = tmp_path / "universe.parquet"
    pd.DataFrame(
        {
            "date": ["2020-01-30", "2020-01-31", "2020-01-31"],
            "stock_id": ["sz.000001", "sz.000001", "sz.000002"],
            "security_name": ["A", "A", "ST B"],
            "trade_status": ["0", "1", "1"],
            "special_treatment": [False, False, True],
        }
    ).to_parquet(universe_path, index=False)
    universe = load_monthly_universe(universe_path)
    assert len(universe) == 2
    assert universe.loc[universe["stock_id"].eq("000001"), "trade_status"].item() == "1"

    month = pd.Period("2020-01", freq="M")
    codes = ["000001", "000002", "000003", "000004"]
    returns = pd.DataFrame(
        {
            "stock_id": codes,
            "month": [month] * 4,
            "date": [pd.Timestamp("2020-01-31")] * 4,
            "target_date": [pd.Timestamp("2020-02-28")] * 4,
            "target_month": [pd.Period("2020-02", freq="M")] * 4,
            "future_return": [0.01] * 4,
            "monthly_return": [0.01] * 4,
            "IVOL": [0.02] * 4,
            "listing_age_days": [np.nan, np.nan, np.nan, 100],
        }
    )
    cap = pd.DataFrame(
        {
            "stock_id": codes,
            "month": [month] * 4,
            "market_cap": [100.0] * 4,
            "size": [5.0] * 4,
        }
    )
    bm = pd.DataFrame(
        {
            "stock_id": codes,
            "month": [month] * 4,
            "pb": [2.0] * 4,
            "bm": [0.5] * 4,
        }
    )
    turnover = pd.DataFrame(
        {
            "stock_id": codes,
            "month": [month] * 4,
            "turnover": [20.0] * 4,
            "turnover_total_shares": [18.0] * 4,
        }
    )
    filter_universe = pd.DataFrame(
        {
            "stock_id": codes,
            "month": [month] * 4,
            "security_name": ["A", "B", "ST C", "D"],
            "trade_status": ["1", "0", "1", "1"],
            "special_treatment": [False, False, True, False],
        }
    )
    filtered, audit = assemble_thesis_v2_panel(
        returns,
        cap,
        bm,
        turnover,
        replace(_config(), exclude_recent_listings_days=365),
        filter_universe,
    )
    assert filtered["stock_id"].tolist() == ["000001"]
    assert audit["excluded_month_end_not_trading"] == 1
    assert audit["excluded_st_months"] == 1
    assert audit["excluded_recent_listing_proxy"] == 1


def test_full_builder_orchestration_and_save(tmp_path: Path, monkeypatch) -> None:
    month = pd.Period("2020-01", freq="M")
    return_ivol = pd.DataFrame(
        {
            "stock_id": ["000001"],
            "month": [month],
            "date": [pd.Timestamp("2020-01-31")],
            "target_date": [pd.Timestamp("2020-02-28")],
            "target_month": [pd.Period("2020-02", freq="M")],
            "target_is_next_calendar_month": [True],
            "monthly_return": [0.01],
            "future_return": [-0.02],
            "IVOL": [0.02],
            "daily_observations": [20],
            "invalid_daily_returns": [0],
            "first_observed_date": [pd.Timestamp("2010-01-04")],
            "listing_age_days": [np.nan],
        }
    )
    cap = pd.DataFrame(
        {
            "stock_id": ["000001"],
            "month": [month],
            "market_cap": [100.0],
            "size": [np.log(100.0)],
        }
    )
    bm = pd.DataFrame(
        {"stock_id": ["000001"], "month": [month], "pb": [2.0], "bm": [0.5]}
    )
    turnover = pd.DataFrame(
        {
            "stock_id": ["000001"],
            "month": [month],
            "turnover": [20.0],
            "turnover_total_shares": [18.0],
        }
    )
    monkeypatch.setattr(
        thesis_v2, "build_return_ivol_panel", lambda _config: return_ivol
    )
    monkeypatch.setattr(thesis_v2, "load_monthly_market_cap", lambda _paths: cap)
    monkeypatch.setattr(thesis_v2, "load_monthly_book_to_market", lambda _paths: bm)
    monkeypatch.setattr(thesis_v2, "load_monthly_turnover", lambda _path: turnover)
    config = ThesisV2Config(
        daily_directory=tmp_path,
        factor_path=tmp_path / "factor.parquet",
        market_cap_paths=(tmp_path / "cap.csv",),
        pb_paths=(tmp_path / "pb.csv",),
        turnover_path=tmp_path / "turnover.xlsx",
        exclude_recent_listings_days=0,
    )
    panel, audit = build_thesis_v2_dataset(config)
    panel_path, audit_path = save_thesis_v2_dataset(panel, audit, tmp_path / "output")
    assert panel_path.exists()
    assert audit_path.exists()
    assert pd.read_parquet(panel_path)["future_return"].item() == -0.02

    risk_free_path = tmp_path / "rf.parquet"
    pd.DataFrame({"date": [pd.Timestamp("2020-01-01")], "RF": [0.001]}).to_parquet(
        risk_free_path, index=False
    )
    rf_return_ivol = return_ivol.assign(future_rf=0.001)
    monkeypatch.setattr(
        thesis_v2, "build_return_ivol_panel", lambda _config: rf_return_ivol
    )
    rf_panel, rf_audit = build_thesis_v2_dataset(
        replace(config, risk_free_path=risk_free_path)
    )
    assert rf_panel["future_return_raw"].item() == -0.02
    assert rf_panel["future_return"].item() == pytest.approx(-0.021)
    assert rf_audit["risk_free_fingerprint"].startswith("sha256:")


def test_assemble_panel_keeps_return_and_size_separate() -> None:
    month = pd.Period("2020-01", freq="M")
    returns = pd.DataFrame(
        {
            "stock_id": ["000001"],
            "month": [month],
            "date": [pd.Timestamp("2020-01-23")],
            "target_date": [pd.Timestamp("2020-02-28")],
            "target_month": [pd.Period("2020-02", freq="M")],
            "target_is_next_calendar_month": [True],
            "monthly_return": [0.03],
            "future_return": [-0.02],
            "IVOL": [0.01],
            "daily_observations": [18],
            "first_observed_date": [pd.Timestamp("2010-01-04")],
            "listing_age_days": [np.nan],
        }
    )
    cap = pd.DataFrame(
        {
            "stock_id": ["000001"],
            "month": [month],
            "market_cap": [100.0],
            "size": [np.log(100.0)],
        }
    )
    bm = pd.DataFrame(
        {"stock_id": ["000001"], "month": [month], "pb": [2.0], "bm": [0.5]}
    )
    turnover = pd.DataFrame(
        {
            "stock_id": ["000001"],
            "month": [month],
            "turnover": [20.0],
            "turnover_total_shares": [18.0],
        }
    )
    panel, audit = assemble_thesis_v2_panel(returns, cap, bm, turnover, _config())
    assert panel.loc[0, "future_return"] == -0.02
    assert panel.loc[0, "size"] == np.log(100.0)
    assert panel.loc[0, "future_return"] != panel.loc[0, "size"]
    assert audit["look_ahead_violations"] == 0
    assert audit["final_rows"] == 1

    industry = pd.DataFrame(
        {
            "stock_id": ["000001"],
            "snapshot_date": [pd.Timestamp("2020-01-01")],
            "industry": ["J66货币金融服务"],
            "financial_industry": [True],
            "real_estate_industry": [False],
            "excluded_industry": [True],
        }
    )
    filtered, industry_audit = assemble_thesis_v2_panel(
        returns,
        cap,
        bm,
        turnover,
        replace(_config(), industry_snapshot_directory=Path("industry")),
        industry_snapshots=industry,
    )
    assert filtered.empty
    assert industry_audit["excluded_financial_industry"] == 1
    assert industry_audit["historical_industry_filter_applied"]
