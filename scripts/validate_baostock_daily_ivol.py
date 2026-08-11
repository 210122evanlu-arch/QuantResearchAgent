"""Validate AKShare IVOL against a stratified BaoStock daily-return sample."""

from __future__ import annotations

# ruff: noqa: RUF001 -- Chinese report prose intentionally uses CJK punctuation.
import json
from datetime import date
from pathlib import Path

import pandas as pd

from data_sources.baostock_returns import (
    BaoStockReturnConfig,
    build_baostock_return_cache,
)
from data_sources.fama_french import FactorDataSet, prepare_five_factor_ivol_panel


def _bao_code(code: str) -> str:
    return ("sh." if code.startswith("6") else "sz.") + code


def select_stratified_codes(panel: pd.DataFrame, per_decile: int = 3) -> list[str]:
    summary = (
        panel.groupby("stock_id", as_index=False)
        .agg(mean_size=("size", "mean"), months=("month", "size"))
        .sort_values(["months", "stock_id"], ascending=[False, True])
    )
    summary["size_decile"] = pd.qcut(
        summary["mean_size"].rank(method="first"), 10, labels=False
    )
    summary["exchange"] = (
        summary["stock_id"]
        .astype(str)
        .str.startswith("6")
        .map({True: "sh", False: "sz"})
    )
    selected_codes: list[str] = []
    for _, decile in summary.groupby("size_decile", sort=True):
        ranked = decile.sort_values(["months", "stock_id"], ascending=[False, True])
        selected = []
        for exchange in ("sh", "sz"):
            exchange_rows = ranked.loc[ranked["exchange"].eq(exchange)]
            if not exchange_rows.empty:
                selected.append(str(exchange_rows.iloc[0]["stock_id"]))
        remaining = ranked.loc[~ranked["stock_id"].astype(str).isin(selected)]
        selected.extend(
            str(code) for code in remaining["stock_id"].head(per_decile - len(selected))
        )
        selected_codes.extend(selected)
    return [_bao_code(code) for code in selected_codes]


def main() -> int:
    prepared = Path("data/prepared")
    panel = pd.read_parquet(
        prepared / "molly_regression_final_v3_baostock_target.parquet"
    )
    codes = select_stratified_codes(panel)
    cache = Path("data/baostock/daily_ivol_validation")
    build_result = build_baostock_return_cache(
        BaoStockReturnConfig(
            codes=tuple(codes),
            start_date=date(2010, 1, 1),
            end_date=date(2025, 12, 31),
            output_directory=cache,
            workers=4,
            frequency="d",
            batch_size=30,
            batch_pause_seconds=0,
        )
    )
    daily_frames = []
    for path in sorted(build_result.stock_directory.glob("*.parquet")):
        frame = pd.read_parquet(path)
        frame = frame.loc[frame["trade_status"].astype(str).eq("1")].copy()
        frame["stock_id"] = frame["stock_id"].str.rsplit(".").str[-1]
        frame = frame.rename(columns={"daily_return": "return"})
        frame["turnover"] = 0.0
        frame["size"] = 1.0
        frame["bm"] = 1.0
        daily_frames.append(
            frame[["date", "stock_id", "return", "turnover", "size", "bm"]]
        )
    daily = pd.concat(daily_frames, ignore_index=True)
    factor_path = Path(
        "data/licensed/csmar/five_factor_daily_123315679/ff5_p9709_2x3_float.parquet"
    )
    factors = FactorDataSet(
        frame=pd.read_parquet(factor_path),
        fingerprint="local-csmar-p9709-validation",
        source_path=factor_path.resolve(),
        metadata={
            "provider": "CSMAR",
            "return_basis": "raw_return_rf_unavailable",
            "residual_ddof": 1,
        },
    )
    bao_panel = prepare_five_factor_ivol_panel(
        daily, factors, minimum_daily_observations=15
    )
    bao_panel["month"] = bao_panel["date"].dt.to_period("M")
    bao_panel = bao_panel.rename(
        columns={"IVOL": "IVOL_baostock", "monthly_return": "return_baostock"}
    )
    ak_panel = pd.read_parquet(prepared / "return_ivol_v2_exchange_limits.parquet")
    ak_panel["month"] = pd.PeriodIndex(ak_panel["month"], freq="M")
    comparison = ak_panel.merge(
        bao_panel[["stock_id", "month", "IVOL_baostock", "return_baostock"]],
        on=["stock_id", "month"],
        how="inner",
        validate="one_to_one",
    )
    comparison = comparison.loc[
        comparison["stock_id"].isin([code[-6:] for code in codes])
    ]
    metrics = {
        "selected_codes": codes,
        "downloaded_codes": build_result.completed_codes,
        "downloaded_daily_rows": build_result.rows,
        "matched_stock_months": len(comparison),
        "ivol_correlation": float(comparison["IVOL"].corr(comparison["IVOL_baostock"])),
        "ivol_median_absolute_difference": float(
            (comparison["IVOL"] - comparison["IVOL_baostock"]).abs().median()
        ),
        "monthly_return_correlation": float(
            comparison["monthly_return"].corr(comparison["return_baostock"])
        ),
    }
    output_json = Path("reports/ivol_baostock_daily_validation.json")
    output_report = Path("reports/ivol_baostock_daily_validation.md")
    output_json.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = [
        "# BaoStock 日频 IVOL 分层样本验证",
        "",
        "该验证从 v3 面板的 10 个市值分位中各选取 3 只历史覆盖较长的股票，以 BaoStock 未复权日收益重新估计相同 CSMAR P9709 五因子 IVOL。",
        "",
        f"- 股票数：{metrics['downloaded_codes']}。",
        f"- BaoStock 日观测：{metrics['downloaded_daily_rows']:,}。",
        f"- 可比股票—月：{metrics['matched_stock_months']:,}。",
        f"- IVOL 相关系数：{metrics['ivol_correlation']:.6f}。",
        f"- IVOL 中位绝对差：{metrics['ivol_median_absolute_difference']:.6f}。",
        f"- 月收益相关系数：{metrics['monthly_return_correlation']:.6f}。",
        "",
        "这是分层验证样本，不代表全市场日频替换。其用途是判断 AKShare 异常月排除后留下的 IVOL 是否与独立收益源大体一致。",
        "",
    ]
    output_report.write_text("\n".join(lines), encoding="utf-8")
    print(f"validation={output_report.resolve()}")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
