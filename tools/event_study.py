"""Deterministic market-model event-study calculations."""

from math import sqrt
from statistics import NormalDist
from typing import Any

import numpy as np
import pandas as pd

from schemas.event_study import (
    DailyAbnormalReturn,
    EventStudyDesign,
    EventStudyResult,
    EventWindowResult,
    ReturnModel,
)

REQUIRED_COLUMNS = {"date", "security_return", "benchmark_return"}


def run_event_study(
    data: pd.DataFrame | list[dict[str, Any]],
    design: EventStudyDesign,
    *,
    contaminated: bool = False,
) -> EventStudyResult:
    """Estimate normal returns and calculate AR/CAR for declared windows."""
    frame = pd.DataFrame(data).copy()
    missing = REQUIRED_COLUMNS - set(frame.columns)
    if missing:
        raise ValueError(
            "event-study data is missing columns: " + ", ".join(sorted(missing))
        )
    frame["date"] = pd.to_datetime(frame["date"], errors="raise").dt.date
    if frame["date"].duplicated().any():
        raise ValueError("event-study data contains duplicate dates")
    frame = frame.sort_values("date").reset_index(drop=True)
    if frame[["security_return", "benchmark_return"]].isna().any().any():
        raise ValueError("event-study returns contain missing values")
    matches = frame.index[frame["date"] == design.event_date].tolist()
    if len(matches) != 1:
        raise ValueError("event_date must match exactly one trading date")
    event_index = matches[0]
    estimation_positions = range(
        event_index + design.estimation_window[0],
        event_index + design.estimation_window[1] + 1,
    )
    if min(estimation_positions) < 0:
        raise ValueError("insufficient pre-event observations for estimation window")
    estimation = frame.iloc[list(estimation_positions)]
    if len(estimation) < 30:
        raise ValueError("event study requires at least 30 estimation observations")

    benchmark = estimation["benchmark_return"].to_numpy(dtype=float)
    security = estimation["security_return"].to_numpy(dtype=float)
    if design.return_model == ReturnModel.MARKET_MODEL:
        matrix = np.column_stack([np.ones(len(benchmark)), benchmark])
        alpha, beta = np.linalg.lstsq(matrix, security, rcond=None)[0]
        residuals = security - (alpha + beta * benchmark)
    else:
        alpha, beta = 0.0, 1.0
        residuals = security - benchmark
    residual_std = float(np.std(residuals, ddof=2))

    lower = min(start for start, _ in design.event_windows)
    upper = max(end for _, end in design.event_windows)
    positions = list(range(event_index + lower, event_index + upper + 1))
    if min(positions) < 0 or max(positions) >= len(frame):
        raise ValueError("event window extends beyond available trading dates")
    event_frame = frame.iloc[positions]
    daily: list[DailyAbnormalReturn] = []
    for relative_day, (_, row) in zip(
        range(lower, upper + 1), event_frame.iterrows(), strict=True
    ):
        expected = float(alpha + beta * row["benchmark_return"])
        abnormal = float(row["security_return"] - expected)
        daily.append(
            DailyAbnormalReturn(
                relative_day=relative_day,
                trading_date=row["date"],
                security_return=float(row["security_return"]),
                benchmark_return=float(row["benchmark_return"]),
                expected_return=expected,
                abnormal_return=abnormal,
            )
        )

    results: list[EventWindowResult] = []
    for start, end in design.event_windows:
        selected = [item for item in daily if start <= item.relative_day <= end]
        cumulative = sum(item.abnormal_return for item in selected)
        standard_error = residual_std * sqrt(len(selected))
        t_stat = cumulative / standard_error if standard_error > 0 else None
        p_value = (
            2 * (1 - NormalDist().cdf(abs(t_stat))) if t_stat is not None else None
        )
        results.append(
            EventWindowResult(
                start_day=start,
                end_day=end,
                observations=len(selected),
                cumulative_abnormal_return=cumulative,
                average_abnormal_return=cumulative / len(selected),
                standard_error=standard_error,
                t_stat=t_stat,
                p_value=p_value,
                significant=(
                    p_value is not None and p_value < design.significance_level
                ),
            )
        )
    warnings = []
    if contaminated:
        warnings.append("The event window contains a potentially overlapping event.")
    significant = [item for item in results if item.significant]
    conclusion = (
        "At least one declared event window has statistically significant abnormal returns."
        if significant
        else "No declared event window has statistically significant abnormal returns."
    )
    return EventStudyResult(
        design=design,
        estimation_observations=len(estimation),
        alpha=float(alpha),
        beta=float(beta),
        residual_std=residual_std,
        window_results=results,
        daily_abnormal_returns=daily,
        contaminated=contaminated,
        warnings=warnings,
        conclusion=conclusion,
    )
