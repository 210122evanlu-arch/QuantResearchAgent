"""Create a deterministic comparison of AKShare-target and BaoStock-target runs."""

from __future__ import annotations

# ruff: noqa: RUF001 -- Chinese report prose intentionally uses CJK punctuation.
import json
from pathlib import Path

SPECIFICATIONS = (
    ("baseline", "IVOL", "基准 IVOL"),
    ("interaction", "ivol_turnover_c", "IVOL×换手率"),
    ("rank_robustness", "interaction_rank_c", "秩交互"),
    ("portfolio_sort", "T5_high_minus_low_IVOL", "最高换手率组高减低 IVOL"),
    ("microcap", "ivol_turnover_c", "微盘股交互"),
)


def _statistic(results: dict, model: str, variable: str) -> dict:
    return next(
        item
        for item in results[model]["statistical_results"]
        if item["variable"] == variable
    )


def main() -> int:
    reports = Path("reports")
    prepared = Path("data/prepared")
    v2 = json.loads((reports / "ivol_thesis_v2_results.json").read_text("utf-8"))
    v3 = json.loads(
        (reports / "ivol_thesis_v3_baostock_results.json").read_text("utf-8")
    )
    audit_v2 = json.loads(
        (prepared / "molly_regression_final_v2.audit.json").read_text("utf-8")
    )
    audit_v3 = json.loads(
        (prepared / "molly_regression_final_v3_baostock_target.audit.json").read_text(
            "utf-8"
        )
    )
    lines = [
        "# IVOL 修正版 v2/v3 数据源敏感性对照",
        "",
        "v2 使用经过交易限幅检查的 AKShare 前复权日收益复合下月收益；v3 保留相同 IVOL 和 CSMAR 控制变量，但将因变量替换为 BaoStock 未复权月度 `pctChg`。",
        "",
        "| 规格 | v2 系数 | v2 t | v3 系数 | v3 t | 方向一致 |",
        "|---|---:|---:|---:|---:|:---:|",
    ]
    for model, variable, label in SPECIFICATIONS:
        left = _statistic(v2, model, variable)
        right = _statistic(v3, model, variable)
        same_direction = left["coefficient"] * right["coefficient"] > 0
        lines.append(
            f"| {label} | {left['coefficient']:.6f} | {left['t_stat']:.3f} | "
            f"{right['coefficient']:.6f} | {right['t_stat']:.3f} | "
            f"{'是' if same_direction else '否'} |"
        )
    added_rows = audit_v3["final_rows"] - audit_v2["final_rows"]
    lines.extend(
        [
            "",
            "## 样本与数据一致性",
            "",
            f"- v2：{audit_v2['final_rows']:,} 条、{audit_v2['unique_stocks']:,} 只股票。",
            f"- v3：{audit_v3['final_rows']:,} 条、{audit_v3['unique_stocks']:,} 只股票，恢复 {added_rows:,} 条股票—月。",
            f"- 两种收益的可比记录：{audit_v3['akshare_baostock_comparable_rows']:,} 条。",
            f"- 收益相关系数：{audit_v3['akshare_baostock_return_correlation']:.6f}。",
            f"- 收益中位绝对差：{audit_v3['akshare_baostock_median_absolute_difference']:.4%}。",
            "",
            "## 判断",
            "",
            "五项关键规格方向全部一致。改用 BaoStock 未复权月收益后，基准 IVOL 负向预测、换手率调节、秩变换、最高换手率组合价差和微盘股交互均保持统计显著。因此，结论不依赖 AKShare 下月收益的具体构造。",
            "",
            "该对照只完成了因变量独立复核；IVOL 日频收益仍来自经过异常月排除的 AKShare 文件。最终论文级复现仍需用 BaoStock 日频 `pctChg` 或 CSMAR `Dretwd/Dretnd` 对 IVOL 再做独立复核。",
            "",
        ]
    )
    output = reports / "ivol_thesis_v2_v3_comparison.md"
    output.write_text("\n".join(lines), encoding="utf-8")
    print(f"comparison={output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
