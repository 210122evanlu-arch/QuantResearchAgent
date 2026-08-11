"""Run the locked thesis specifications on the corrected v2 monthly panel."""

# ruff: noqa: RUF001 -- Chinese report prose intentionally uses CJK punctuation.

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from tools.thesis_ivol import prepare_thesis_ivol_features
from tools.thesis_replication import run_thesis_replication_suite


def _result_rows(results: dict) -> list[str]:
    rows = [
        "| 规格 | 变量 | 系数 | t 值 | p 值 | 显著 | 样本量 | 平均调整 R² |",
        "|---|---|---:|---:|---:|:---:|---:|---:|",
    ]
    for name, result in results.items():
        adjusted = result.model_metrics.adjusted_r_squared
        for statistic in result.statistical_results:
            rows.append(
                "| {name} | {variable} | {coefficient:.6f} | {t_stat:.3f} | "
                "{p_value:.4f} | {significant} | {sample_size:,} | {adjusted} |".format(
                    name=name,
                    variable=statistic.variable,
                    coefficient=statistic.coefficient,
                    t_stat=statistic.t_stat,
                    p_value=statistic.p_value,
                    significant="是" if statistic.significant else "否",
                    sample_size=result.sample_size,
                    adjusted=(f"{adjusted:.4f}" if adjusted is not None else "—"),
                )
            )
    return rows


def _statistic(results: dict, model: str, variable: str):
    return next(
        item for item in results[model].statistical_results if item.variable == variable
    )


def build_report(audit: dict, results: dict) -> str:
    baseline = _statistic(results, "baseline", "IVOL")
    interaction = _statistic(results, "interaction", "ivol_turnover_c")
    rank = _statistic(results, "rank_robustness", "interaction_rank_c")
    portfolio_high_turnover = _statistic(
        results, "portfolio_sort", "T5_high_minus_low_IVOL"
    )
    baseline_text = (
        "支持" if baseline.coefficient < 0 and baseline.significant else "不支持"
    )
    interaction_text = (
        "支持" if interaction.coefficient < 0 and interaction.significant else "不支持"
    )
    target_provider = audit.get(
        "target_return_provider", "AKShare qfq close, validated daily compounding"
    )
    uses_risk_free = bool(audit.get("risk_free_source"))
    uses_industry_filter = bool(audit.get("historical_industry_filter_applied"))
    if uses_risk_free and uses_industry_filter:
        version = "v5（RF 与历史行业修正）"
    elif uses_risk_free:
        version = "v4（RF 超额收益修正）"
    elif "BaoStock" in target_provider:
        version = "v3（BaoStock 收益复核）"
    else:
        version = "v2"
    target_description = (
        f"{target_provider} 扣除对应月累计 RF" if uses_risk_free else target_provider
    )
    ivol_return_basis = "日超额收益" if uses_risk_free else "日收益"
    lines = [
        f"# A股特质波动率之谜：修正版 {version} 复现报告",
        "",
        f"> 本报告使用本地授权 CSMAR 因子、估值与换手率数据、本地 AKShare 日行情构造 IVOL，并使用 {target_description} 构造下月收益。它是可审计的研究中间结果，不是投资建议，也不是对原论文结论的最终确认。",
        "",
        "## 执行摘要",
        "",
        f"修正旧脚本将市值增长误作收益率的问题后，基准 Fama–MacBeth 回归对“高 IVOL 预测较低下月收益”的假设{baseline_text}：IVOL 系数为 {baseline.coefficient:.6f}，t={baseline.t_stat:.3f}，p={baseline.p_value:.4f}。",
        f"中心化换手率交互项对“交易信念/换手率强化 IVOL 折价”的假设{interaction_text}：交互项系数为 {interaction.coefficient:.6f}，t={interaction.t_stat:.3f}，p={interaction.p_value:.4f}；秩变换交互项系数为 {rank.coefficient:.6f}（t={rank.t_stat:.3f}）。",
        f"最高换手率组内，高 IVOL 组合减去低 IVOL 组合的下月收益差为 {portfolio_high_turnover.coefficient:.4%}（t={portfolio_high_turnover.t_stat:.3f}）。",
        "",
        "## 数据与样本",
        "",
        f"- 最终样本：{audit['final_rows']:,} 个股票—月，{audit['unique_stocks']:,} 只股票，{audit['start_month']} 至 {audit['end_month']}。",
        f"- IVOL：本地 AKShare 前复权日收盘价配合 CSMAR P9709 五因子，以{ivol_return_basis}估计月度残差波动率，月内至少 15 个有效交易日，残差标准差 ddof={audit['residual_ddof']}。",
        f"- 下月收益：{target_description}。",
        f"- RF 处理：{audit['risk_free_treatment']}。",
        "- 控制变量：CSMAR 月末总市值的自然对数（Size）、正 PB 的倒数（BM）；换手率采用 CSMAR ToverOsM，即月内流通股日换手率之和（%）。",
        f"- 异常复权处理：识别 {audit['invalid_daily_observations_detected']:,} 个违反交易限幅或价格链接失效的日观测，并整月排除 {audit['invalid_stock_months_excluded']:,} 个受影响股票—月。",
        f"- 样本筛选：月末非交易 {audit['excluded_month_end_not_trading']:,} 条、ST {audit['excluded_st_months']:,} 条、可识别上市不足一年 {audit['excluded_recent_listing_proxy']:,} 条。",
        (
            f"- 历史行业筛选：按半年 BaoStock 证监会行业快照向后匹配，剔除金融 {audit['excluded_financial_industry']:,} 条、房地产 {audit['excluded_real_estate_industry']:,} 条；行业未知 {audit['rows_without_known_historical_industry']:,} 条保留并披露。"
            if uses_industry_filter
            else "- 历史行业筛选：尚未执行。"
        ),
        f"- 数据契约检查：重复股票—月 {audit['duplicate_stock_months']}；关键字段缺失 {audit['missing_required_values']}；前视违规 {audit['look_ahead_violations']}。",
        "",
        "## 模型",
        "",
        "主检验为逐月截面回归并对月度平均斜率使用 Newey–West（3 阶滞后）推断：",
        "",
        "`ExcessReturn(i,t+1) = α_t + β1 IVOL(i,t) + β2 Size(i,t) + β3 BM(i,t) + ε(i,t+1)`"
        if uses_risk_free
        else "`Return(i,t+1) = α_t + β1 IVOL(i,t) + β2 Size(i,t) + β3 BM(i,t) + ε(i,t+1)`",
        "",
        "交互模型加入月度截面中心化的 IVOL、换手率及二者乘积；另做秩变换、微盘股子样本和先换手率后 IVOL 的 5×5 等权组合排序。连续解释变量按全样本 1%/99% 缩尾。",
        "",
        "## 完整结果",
        "",
        *_result_rows(results),
        "",
        "## 与旧 Notebook 的关系",
        "",
        "旧 Notebook 的最终 M3 曾报告 IVOL×换手率系数 -0.0303（t=-3.30），秩交互项 -0.0353（t=-6.23）。但旧数据中的 `ret` 被定义为 `size.pct_change()`，`next_ret` 因而是下月市值增长，而不是真实股票收益；此外旧样本混入了 P9709 因子不覆盖的科创板和北交所股票。因此旧系数只能作为代码迁移对照，不能作为经济结论与本报告直接比较。",
        "",
        "## 风险与尚未解决的问题",
        "",
        "- 生存偏差：本地 AKShare 日行情目录由当期股票列表抓取，历史退市公司可能缺失。",
        "- IVOL 源限制：AKShare 前复权历史含负值/近零价格，本版保守排除违反交易限幅的整月；30 只沪深、市值分层股票的 BaoStock 日频复核得到 0.9919 的 IVOL 相关系数，但最终论文版仍应使用 CSMAR `Dretwd/Dretnd` 或全市场、无生存偏差的日频数据重建。",
        "- 无风险利率：本版已按论文公式实现 `R-Rf`，但使用的是中债 3 个月国债收益率代理，而非原研究所用的 CSMAR RF 序列。"
        if uses_risk_free
        else "- 无风险利率：现有 CSMAR 五因子导出不含 RF，本版以含截距的原始股票收益回归作为兼容处理，尚未严格实现 `R-Rf`。",
        "- 行业筛选：已使用半年点时证监会行业快照剔除金融和房地产，但半年频率可能延迟识别期中行业变更，且尚未加入行业固定效应。"
        if uses_industry_filter
        else "- 行业筛选：缺少历史点时行业分类，尚未执行金融/房地产行业排除或行业固定效应。",
        "- 因果识别：Fama–MacBeth 和组合排序识别预测关系，不足以证明投资者信念差异的因果机制。",
        "",
        "## 结论",
        "",
        f"在上述修正样本与限制下，基准 IVOL 假设{baseline_text}，换手率调节假设{interaction_text}。是否能称为论文层面的稳健复现，仍取决于使用无生存偏差的原始日收益、原始 CSMAR RF，并以更细频率的权威历史行业口径复核后结果是否保持。",
        "",
    ]
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--panel",
        type=Path,
        default=Path("data/prepared/molly_regression_final_v2.parquet"),
    )
    parser.add_argument(
        "--audit",
        type=Path,
        default=Path("data/prepared/molly_regression_final_v2.audit.json"),
    )
    parser.add_argument(
        "--results",
        type=Path,
        default=Path("reports/ivol_thesis_v2_results.json"),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("reports/ivol_thesis_v2_report.md"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    panel_path = args.panel
    audit_path = args.audit
    output_json = args.results
    output_report = args.report
    panel = pd.read_parquet(panel_path)
    features = prepare_thesis_ivol_features(panel)
    results = run_thesis_replication_suite(features)
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps(
            {name: result.model_dump(mode="json") for name, result in results.items()},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    output_report.write_text(build_report(audit, results), encoding="utf-8")
    print(f"results={output_json.resolve()}")
    print(f"report={output_report.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
