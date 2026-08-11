import numpy as np
import pandas as pd

from tools.thesis_ivol import prepare_thesis_ivol_features
from tools.thesis_replication import (
    run_thesis_replication_suite,
    thesis_model_1,
    thesis_model_3,
    thesis_portfolio_model,
    thesis_rank_model,
)


def test_thesis_models_are_locked_to_declared_variables() -> None:
    baseline = thesis_model_1()
    interaction = thesis_model_3()
    rank = thesis_rank_model()
    portfolio = thesis_portfolio_model()

    assert baseline.formula == "future_return ~ IVOL + size + bm"
    assert interaction.formula == (
        "future_return ~ IVOL_c + turnover_c + ivol_turnover_c + size + bm"
    )
    assert rank.formula == (
        "future_return ~ IVOL_rank_c + turnover_rank_c + interaction_rank_c + size + bm"
    )
    assert portfolio.formula == "future_return ~ turnover + IVOL"
    assert portfolio.estimator.value == "portfolio_sort"


def test_locked_thesis_suite_runs_all_four_specifications() -> None:
    rng = np.random.default_rng(2026)
    rows = []
    for month in pd.date_range("2023-01-31", periods=8, freq="ME"):
        for stock in range(30):
            rows.append(
                {
                    "stock_id": f"S{stock:02d}",
                    "date": month,
                    "future_return": float(rng.normal(0.01, 0.05)),
                    "IVOL": float(rng.uniform(0.01, 0.05)),
                    "turnover": float(rng.uniform(0.5, 12.0)),
                    "size": float(rng.normal(16, 1)),
                    "bm": float(rng.uniform(0.1, 1.5)),
                }
            )
    panel = prepare_thesis_ivol_features(pd.DataFrame(rows))

    results = run_thesis_replication_suite(panel)

    assert set(results) == {
        "baseline",
        "interaction",
        "rank_robustness",
        "portfolio_sort",
        "microcap",
    }
    assert results["baseline"].sample_size == 240
    assert results["microcap"].sample_size == 72
