"""Non-IVOL momentum research fixture using fixed effects and backtesting."""

from pathlib import Path

import numpy as np
import pandas as pd

from schemas.model_design import ModelDesign
from tools.statistics import ExperimentConfig, run_backtest, run_ols


def _panel() -> pd.DataFrame:
    rng = np.random.default_rng(20260811)
    rows = []
    entities = [f"S{index:03d}" for index in range(60)]
    entity_effects = dict(
        zip(entities, rng.normal(0, 0.003, len(entities)), strict=True)
    )
    persistent_scores = dict(
        zip(entities, rng.normal(0, 1, len(entities)), strict=True)
    )
    for date in pd.date_range("2023-01-31", periods=30, freq="ME"):
        market_shock = rng.normal(0, 0.002)
        for entity in entities:
            momentum = 0.7 * persistent_scores[entity] + rng.normal(0, 0.35)
            future_return = (
                0.002 * momentum
                + entity_effects[entity]
                + market_shock
                + rng.normal(0, 0.015)
            )
            rows.append(
                {
                    "date": date,
                    "stock_id": entity,
                    "momentum_12_1": momentum,
                    "future_return": future_return,
                }
            )
    return pd.DataFrame(rows)


def _model(*, estimator: str, fixed_effects: list[str]) -> ModelDesign:
    return ModelDesign.model_validate(
        {
            "model_name": "Cross-sectional momentum return prediction",
            "formula": "future_return ~ momentum_12_1",
            "estimator": estimator,
            "dependent_variable": {
                "name": "future_return",
                "role": "dependent",
                "definition": "Next-month stock return",
            },
            "independent_variables": [
                {
                    "name": "momentum_12_1",
                    "role": "independent",
                    "definition": "Return momentum excluding the most recent month",
                    "expected_sign": "positive",
                }
            ],
            "control_variables": [],
            "fixed_effects": fixed_effects,
            "standard_error_method": "HC3",
            "assumptions": ["Signal is observed before the return period"],
            "endogeneity_strategy": ["Lagged predictor and entity fixed effects"],
            "limitations": ["Synthetic fixture; not evidence of a live-market anomaly"],
        }
    )


def _render(regression, backtest) -> str:
    coefficient = regression.statistical_results[0]
    metrics = backtest.model_metrics
    annualized_return = metrics.annualized_return
    annualized_volatility = metrics.annualized_volatility
    sharpe_ratio = metrics.sharpe_ratio
    max_drawdown = metrics.max_drawdown
    average_turnover = metrics.average_turnover
    win_rate = metrics.win_rate
    assert annualized_return is not None
    assert annualized_volatility is not None
    assert sharpe_ratio is not None
    assert max_drawdown is not None
    assert average_turnover is not None
    assert win_rate is not None
    return "\n".join(
        [
            '<div align="center">',
            "",
            "<h1>动量因子预测能力研究</h1>",
            "",
            "<p><strong>Non-IVOL Generalisation Demo</strong><br>",
            "合成面板 · 实体固定效应 · 多空组合回测</p>",
            "",
            "</div>",
            "",
            "## 研究问题",
            "",
            "过去收益动量是否正向预测下一期股票收益？",
            "",
            "## 实验设计",
            "",
            "- 回归：实体固定效应 OLS，HC3 稳健标准误。",
            "- 回测：按动量信号分为五组，等权做多最高组、做空最低组。",
            "- 交易成本：单次换仓 10 bps；月度调仓。",
            "- 数据：确定性生成的合成许可测试面板，不代表真实市场结论。",
            "",
            "## 结构化结果",
            "",
            "| 检验 | 结果 |",
            "| --- | ---: |",
            f"| 固定效应回归系数 | {coefficient.coefficient:.4f} |",
            f"| 回归 p-value | {coefficient.p_value:.4g} |",
            f"| 回测年化收益 | {annualized_return:.2%} |",
            f"| 回测年化波动率 | {annualized_volatility:.2%} |",
            f"| Sharpe Ratio | {sharpe_ratio:.2f} |",
            f"| 最大回撤 | {max_drawdown:.2%} |",
            f"| 平均换手率 | {average_turnover:.2%} |",
            f"| 月度胜率 | {win_rate:.2%} |",
            "",
            "## 结论与边界",
            "",
            "该案例证明 ModelDesign 可以将非 IVOL 变量路由至固定效应和 Backtest "
            "执行器，并以统一 ExperimentResult 返回结果。由于使用合成数据，本报告"
            "只验证平台通用性，不主张真实市场存在动量异常。",
            "",
        ]
    )


def run_momentum_factor_demo(report_path: str | Path | None = None):
    frame = _panel()
    config = ExperimentConfig(
        portfolio_groups=5,
        transaction_cost_bps=10,
        periods_per_year=12,
    )
    regression = run_ols(
        frame, _model(estimator="ols", fixed_effects=["stock_id"]), config
    )
    backtest = run_backtest(
        frame,
        _model(estimator="backtest", fixed_effects=[]),
        config,
        date_column="date",
    )
    target = (
        Path(report_path)
        if report_path
        else (
            Path(__file__).resolve().parents[1]
            / "reports"
            / "quant_research"
            / "momentum_factor_demo.md"
        )
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(_render(regression, backtest), encoding="utf-8")
    return regression, backtest, target.resolve()


if __name__ == "__main__":
    regression_result, backtest_result, output = run_momentum_factor_demo()
    print("Regression:", regression_result.conclusion)
    print("Backtest:", backtest_result.conclusion)
    print("Report:", output)
