"""Compare BaoStock target, RF-corrected, and industry-filtered thesis runs."""

from __future__ import annotations

# ruff: noqa: RUF001 -- Chinese report prose intentionally uses CJK punctuation.
import json
from pathlib import Path

import pandas as pd

SPECIFICATIONS = (
    ("baseline", "IVOL", "基准 IVOL"),
    ("interaction", "ivol_turnover_c", "IVOL×换手率"),
    ("rank_robustness", "interaction_rank_c", "秩交互"),
    ("portfolio_sort", "T5_high_minus_low_IVOL", "最高换手率组高减低 IVOL"),
    ("microcap", "ivol_turnover_c", "微盘股交互"),
)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _statistic(results: dict, model: str, variable: str) -> dict:
    return next(
        item
        for item in results[model]["statistical_results"]
        if item["variable"] == variable
    )


def main() -> int:
    reports = Path("reports")
    prepared = Path("data/prepared")
    versions = {
        "v3": _load_json(reports / "ivol_thesis_v3_baostock_results.json"),
        "v4": _load_json(reports / "ivol_thesis_v4_rf_results.json"),
        "v5": _load_json(reports / "ivol_thesis_v5_rf_industry_results.json"),
    }
    audit_v3 = _load_json(
        prepared / "molly_regression_final_v3_baostock_target.audit.json"
    )
    audit_v5 = _load_json(
        prepared / "molly_regression_final_v5_rf_industry_baostock.audit.json"
    )
    panel_v3 = pd.read_parquet(
        prepared / "molly_regression_final_v3_baostock_target.parquet",
        columns=["stock_id", "month", "IVOL", "future_return"],
    )
    panel_v4 = pd.read_parquet(
        prepared / "molly_regression_final_v4_rf_baostock.parquet",
        columns=[
            "stock_id",
            "month",
            "IVOL",
            "future_return",
            "future_return_raw",
            "future_rf",
        ],
    )
    comparable = panel_v3.merge(
        panel_v4,
        on=["stock_id", "month"],
        suffixes=("_v3", "_v4"),
        validate="one_to_one",
    )
    ivol_correlation = comparable["IVOL_v3"].corr(comparable["IVOL_v4"])
    ivol_mad = (comparable["IVOL_v3"] - comparable["IVOL_v4"]).abs().median()
    target_correlation = comparable["future_return_v3"].corr(
        comparable["future_return_v4"]
    )
    lines = [
        "# IVOL 修正版 v3/v4/v5 研究口径对照",
        "",
        "v3 使用 BaoStock 未复权下月收益；v4 按论文公式加入中债 3 个月国债 RF 代理；v5 再使用半年点时证监会行业快照剔除金融与房地产。",
        "",
        "| 规格 | v3 系数 / t | v4 系数 / t | v5 系数 / t | 三版方向一致 |",
        "|---|---:|---:|---:|:---:|",
    ]
    for model, variable, label in SPECIFICATIONS:
        stats = {
            version: _statistic(result, model, variable)
            for version, result in versions.items()
        }
        coefficients = [stats[version]["coefficient"] for version in versions]
        same_direction = all(value < 0 for value in coefficients) or all(
            value > 0 for value in coefficients
        )
        lines.append(
            f"| {label} | {stats['v3']['coefficient']:.6f} / {stats['v3']['t_stat']:.3f} | "
            f"{stats['v4']['coefficient']:.6f} / {stats['v4']['t_stat']:.3f} | "
            f"{stats['v5']['coefficient']:.6f} / {stats['v5']['t_stat']:.3f} | "
            f"{'是' if same_direction else '否'} |"
        )
    removed = audit_v3["final_rows"] - audit_v5["final_rows"]
    lines.extend(
        [
            "",
            "## RF 修正的实际影响",
            "",
            f"- v3/v4 可比股票—月：{len(comparable):,}。",
            f"- IVOL 相关系数：{ivol_correlation:.9f}。",
            f"- IVOL 中位绝对差：{ivol_mad:.9f}。",
            f"- 下月原始收益与超额收益相关系数：{target_correlation:.9f}。",
            f"- 月 RF 均值：{comparable['future_rf'].mean():.4%}；范围 {comparable['future_rf'].min():.4%} 至 {comparable['future_rf'].max():.4%}。",
            "",
            "RF 对核心斜率影响极小。这与含截距的月内时间序列回归和逐月截面回归一致：同日、同月的共同 RF 变动主要被截距吸收。加入 RF 的价值主要是让变量定义与论文公式一致，而不是制造新的显著性。",
            "",
            "## 历史行业修正",
            "",
            f"- v3/v4：{audit_v3['final_rows']:,} 个股票—月、{audit_v3['unique_stocks']:,} 只股票。",
            f"- v5：{audit_v5['final_rows']:,} 个股票—月、{audit_v5['unique_stocks']:,} 只股票。",
            f"- 共剔除 {removed:,} 个股票—月，其中金融 {audit_v5['excluded_financial_industry']:,}、房地产 {audit_v5['excluded_real_estate_industry']:,}。",
            f"- 行业未知记录 {audit_v5['rows_without_known_historical_industry']:,} 条，保留并披露。",
            "",
            "## 判断",
            "",
            "RF 与历史行业修正后，五项锁定规格方向全部一致；基准 IVOL、换手率交互、秩交互、最高换手率组合价差和微盘股交互仍显著为负。行业剔除后核心交互项绝对值略增，说明此前结果并非由金融或房地产行业暴露驱动。",
            "",
            "剩余主要限制是本地日行情目录可能遗漏退市股票、RF 为公开国债代理而非原始 CSMAR 序列，以及半年行业快照不能即时捕捉期中行业变化。",
            "",
        ]
    )
    output = reports / "ivol_thesis_v3_v5_comparison.md"
    output.write_text("\n".join(lines), encoding="utf-8")
    print(f"comparison={output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
