from pathlib import Path

from examples.momentum_factor_demo import run_momentum_factor_demo


def test_non_ivol_momentum_demo_runs_two_estimators(tmp_path: Path) -> None:
    regression, backtest, report = run_momentum_factor_demo(tmp_path / "momentum.md")
    assert regression.parameters["fixed_effects"] == "stock_id"
    assert regression.statistical_results[0].variable == "momentum_12_1"
    assert backtest.parameters["signal"] == "momentum_12_1"
    assert backtest.model_metrics.annualized_return > 0
    assert report.is_file()
    content = report.read_text(encoding="utf-8")
    assert "Non-IVOL Generalisation Demo" in content
    assert "只验证平台通用性" in content
