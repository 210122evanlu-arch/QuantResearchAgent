"""Deterministic regression engines for financial experiments."""

from dataclasses import dataclass

import numpy as np
import pandas as pd
import statsmodels.api as sm

from schemas.enums import Estimator
from schemas.experiment import (
    ExperimentResult,
    ModelMetrics,
    PortfolioCellResult,
    RobustnessCheck,
    StatisticalResult,
)
from schemas.model_design import ModelDesign


class ExperimentEngineError(ValueError):
    """Raised when an estimator cannot be run safely on the supplied sample."""


class UnsupportedEstimatorError(ExperimentEngineError):
    """Raised instead of silently substituting another estimator."""


@dataclass(frozen=True)
class ExperimentConfig:
    significance_level: float = 0.05
    hac_maxlags: int = 3
    minimum_fama_macbeth_periods: int = 3
    portfolio_groups: int = 5
    portfolio_primary_variable: str = "turnover"
    portfolio_secondary_variable: str = "IVOL"

    def __post_init__(self) -> None:
        if not 0 < self.significance_level < 1:
            raise ValueError("significance_level must be between 0 and 1")
        if self.hac_maxlags < 0:
            raise ValueError("hac_maxlags must be non-negative")
        if self.minimum_fama_macbeth_periods < 2:
            raise ValueError("minimum_fama_macbeth_periods must be at least 2")
        if not 2 <= self.portfolio_groups <= 10:
            raise ValueError("portfolio_groups must be between 2 and 10")
        if (
            self.portfolio_primary_variable.casefold()
            == self.portfolio_secondary_variable.casefold()
        ):
            raise ValueError("portfolio sort variables must be different")


def _model_columns(model: ModelDesign) -> tuple[str, list[str]]:
    dependent = model.dependent_variable.name
    regressors = [
        *(variable.name for variable in model.independent_variables),
        *(variable.name for variable in model.control_variables),
    ]
    return dependent, regressors


def _complete_sample(
    frame: pd.DataFrame,
    dependent: str,
    regressors: list[str],
    extra_columns: list[str] | None = None,
) -> tuple[pd.DataFrame, int]:
    columns = [dependent, *regressors, *(extra_columns or [])]
    missing = sorted(set(columns).difference(frame.columns))
    if missing:
        raise ExperimentEngineError(
            "Experiment data is missing columns: " + ", ".join(missing)
        )
    sample = frame[columns].dropna().copy()
    dropped = len(frame) - len(sample)
    if sample.empty:
        raise ExperimentEngineError("No complete observations remain for estimation")
    return sample, dropped


def _covariance_settings(method: str, maxlags: int) -> tuple[str, dict]:
    normalised = method.strip().casefold().replace("_", "-")
    if "newey" in normalised or "hac" in normalised:
        return "HAC", {"maxlags": maxlags}
    if "hc3" in normalised or normalised in {"robust", "heteroskedasticity-robust"}:
        return "HC3", {}
    if normalised in {"nonrobust", "classical", "ols"}:
        return "nonrobust", {}
    raise ExperimentEngineError(f"Unsupported standard_error_method: {method!r}")


def _fit_ols(y: pd.Series, x: pd.DataFrame, cov_type: str, cov_kwds: dict):
    design = sm.add_constant(x.astype(float), has_constant="add")
    if len(design) <= design.shape[1]:
        raise ExperimentEngineError(
            "OLS requires more complete observations than fitted parameters"
        )
    if np.linalg.matrix_rank(design.to_numpy()) < design.shape[1]:
        raise ExperimentEngineError("OLS design matrix is rank deficient")
    model = sm.OLS(y.astype(float), design)
    if cov_type == "nonrobust":
        return model.fit(use_t=True)
    return model.fit(cov_type=cov_type, cov_kwds=cov_kwds, use_t=True)


def _statistical_results(results, variables: list[str], alpha: float):
    intervals = results.conf_int(alpha=alpha)
    output = []
    for variable in variables:
        values = np.asarray(
            [
                results.params[variable],
                results.bse[variable],
                results.tvalues[variable],
                results.pvalues[variable],
                intervals.loc[variable, 0],
                intervals.loc[variable, 1],
            ],
            dtype=float,
        )
        if not np.isfinite(values).all():
            raise ExperimentEngineError(
                f"Non-finite OLS inference for variable {variable!r}"
            )
        output.append(
            StatisticalResult(
                variable=variable,
                coefficient=float(values[0]),
                standard_error=float(values[1]),
                t_stat=float(values[2]),
                p_value=float(values[3]),
                confidence_interval=(float(values[4]), float(values[5])),
                significant=bool(values[3] < alpha),
            )
        )
    return output


def _information_coefficient(y: pd.Series, fitted: pd.Series) -> float | None:
    if len(y) < 2 or y.nunique() < 2 or fitted.nunique() < 2:
        return None
    value = float(np.corrcoef(y.to_numpy(), fitted.to_numpy())[0, 1])
    return value if np.isfinite(value) else None


def run_ols(
    frame: pd.DataFrame,
    model: ModelDesign,
    config: ExperimentConfig,
    *,
    data_fingerprint: str | None = None,
) -> ExperimentResult:
    if model.fixed_effects:
        raise UnsupportedEstimatorError(
            "OLS fixed effects are not implemented in the Round 4 engine"
        )
    dependent, regressors = _model_columns(model)
    sample, dropped = _complete_sample(frame, dependent, regressors)
    cov_type, cov_kwds = _covariance_settings(
        model.standard_error_method, config.hac_maxlags
    )
    results = _fit_ols(sample[dependent], sample[regressors], cov_type, cov_kwds)
    statistics = _statistical_results(results, regressors, config.significance_level)

    alternative_cov = "nonrobust" if cov_type == "HC3" else "HC3"
    alternative = _fit_ols(sample[dependent], sample[regressors], alternative_cov, {})
    stability = all(
        bool(results.pvalues[name] < config.significance_level)
        == bool(alternative.pvalues[name] < config.significance_level)
        for name in regressors
    )
    robustness = RobustnessCheck(
        name="Alternative covariance estimator",
        method=f"Compare {cov_type} inference with {alternative_cov}",
        result=(
            "Significance classifications are stable"
            if stability
            else "At least one significance classification changes"
        ),
        passed=stability,
    )
    warnings = []
    if dropped:
        warnings.append(f"Dropped {dropped} rows with missing model values.")
    significant = [result.variable for result in statistics if result.significant]
    conclusion = (
        "Statistically significant variables: " + ", ".join(significant)
        if significant
        else "No model variable is statistically significant at the configured level."
    )
    residuals = np.asarray(results.resid, dtype=float)
    return ExperimentResult(
        method=f"OLS with {cov_type} covariance",
        estimator=Estimator.OLS,
        sample_size=len(sample),
        significance_level=config.significance_level,
        model_metrics=ModelMetrics(
            r_squared=float(results.rsquared),
            adjusted_r_squared=float(results.rsquared_adj),
            observations=len(sample),
            rmse=float(np.sqrt(np.mean(np.square(residuals)))),
            information_coefficient=_information_coefficient(
                sample[dependent], pd.Series(results.fittedvalues, index=sample.index)
            ),
        ),
        statistical_results=statistics,
        robustness_checks=[robustness],
        warnings=warnings,
        conclusion=conclusion,
        data_fingerprint=data_fingerprint,
        parameters={
            "covariance_type": cov_type,
            "hac_maxlags": config.hac_maxlags,
            "intercept": True,
        },
    )


def run_fama_macbeth(
    frame: pd.DataFrame,
    model: ModelDesign,
    config: ExperimentConfig,
    *,
    date_column: str,
    data_fingerprint: str | None = None,
) -> ExperimentResult:
    if model.fixed_effects:
        raise UnsupportedEstimatorError(
            "Fama-MacBeth fixed effects are not implemented in the Round 4 engine"
        )
    primary_cov, _ = _covariance_settings(
        model.standard_error_method, config.hac_maxlags
    )
    if primary_cov not in {"HAC", "nonrobust"}:
        raise ExperimentEngineError(
            "Fama-MacBeth supports Newey-West/HAC or nonrobust time-series inference"
        )
    dependent, regressors = _model_columns(model)
    sample, dropped = _complete_sample(frame, dependent, regressors, [date_column])
    sample[date_column] = pd.to_datetime(sample[date_column], errors="coerce")
    if sample[date_column].isna().any():
        raise ExperimentEngineError("Fama-MacBeth date column contains invalid values")

    coefficients: list[pd.Series] = []
    r_squared: list[float] = []
    adjusted_r_squared: list[float] = []
    all_residuals: list[float] = []
    all_actual: list[float] = []
    all_fitted: list[float] = []
    skipped_periods = 0
    used_observations = 0
    for _, period in sample.groupby(date_column, sort=True):
        try:
            fitted = _fit_ols(period[dependent], period[regressors], "nonrobust", {})
        except ExperimentEngineError:
            skipped_periods += 1
            continue
        coefficients.append(fitted.params)
        r_squared.append(float(fitted.rsquared))
        adjusted_r_squared.append(float(fitted.rsquared_adj))
        all_residuals.extend(np.asarray(fitted.resid, dtype=float))
        all_actual.extend(period[dependent].astype(float).tolist())
        all_fitted.extend(np.asarray(fitted.fittedvalues, dtype=float))
        used_observations += len(period)

    if len(coefficients) < config.minimum_fama_macbeth_periods:
        raise ExperimentEngineError(
            "Too few valid cross-sectional periods for Fama-MacBeth inference"
        )
    coefficient_frame = pd.DataFrame(coefficients)
    maxlags = min(config.hac_maxlags, len(coefficient_frame) - 1)
    statistics: list[StatisticalResult] = []
    alternative_significance: dict[str, bool] = {}
    for variable in regressors:
        series = coefficient_frame[variable].astype(float)
        constant = np.ones((len(series), 1))
        if primary_cov == "HAC":
            primary = sm.OLS(series.to_numpy(), constant).fit(
                cov_type="HAC", cov_kwds={"maxlags": maxlags}, use_t=True
            )
        else:
            primary = sm.OLS(series.to_numpy(), constant).fit(use_t=True)
        if primary_cov == "HAC":
            alternative = sm.OLS(series.to_numpy(), constant).fit(use_t=True)
        else:
            alternative = sm.OLS(series.to_numpy(), constant).fit(
                cov_type="HAC", cov_kwds={"maxlags": maxlags}, use_t=True
            )
        interval = primary.conf_int(alpha=config.significance_level)[0]
        p_value = float(primary.pvalues[0])
        inference_values = np.asarray(
            [
                primary.params[0],
                primary.bse[0],
                primary.tvalues[0],
                p_value,
                interval[0],
                interval[1],
            ],
            dtype=float,
        )
        if not np.isfinite(inference_values).all():
            raise ExperimentEngineError(
                f"Non-finite Fama-MacBeth inference for variable {variable!r}"
            )
        statistics.append(
            StatisticalResult(
                variable=variable,
                coefficient=float(primary.params[0]),
                standard_error=float(primary.bse[0]),
                t_stat=float(primary.tvalues[0]),
                p_value=p_value,
                confidence_interval=(float(interval[0]), float(interval[1])),
                significant=bool(p_value < config.significance_level),
            )
        )
        alternative_significance[variable] = bool(
            alternative.pvalues[0] < config.significance_level
        )

    stability = all(
        result.significant == alternative_significance[result.variable]
        for result in statistics
    )
    warnings = []
    if dropped:
        warnings.append(f"Dropped {dropped} rows with missing model values.")
    if skipped_periods:
        warnings.append(
            f"Skipped {skipped_periods} periods with insufficient or singular data."
        )
    significant = [result.variable for result in statistics if result.significant]
    return ExperimentResult(
        method=(
            "Fama-MacBeth cross-sectional regressions with "
            f"{primary_cov} time-series inference"
        ),
        estimator=Estimator.FAMA_MACBETH,
        sample_size=used_observations,
        significance_level=config.significance_level,
        model_metrics=ModelMetrics(
            r_squared=float(np.mean(r_squared)),
            adjusted_r_squared=float(np.mean(adjusted_r_squared)),
            observations=used_observations,
            rmse=float(np.sqrt(np.mean(np.square(all_residuals)))),
            information_coefficient=_information_coefficient(
                pd.Series(all_actual), pd.Series(all_fitted)
            ),
        ),
        statistical_results=statistics,
        robustness_checks=[
            RobustnessCheck(
                name="Fama-MacBeth covariance sensitivity",
                method="Compare HAC and nonrobust time-series inference",
                result=(
                    "Significance classifications are stable"
                    if stability
                    else "At least one significance classification changes"
                ),
                passed=stability,
            )
        ],
        warnings=warnings,
        conclusion=(
            "Statistically significant average slopes: " + ", ".join(significant)
            if significant
            else "No average slope is statistically significant at the configured level."
        ),
        data_fingerprint=data_fingerprint,
        parameters={
            "periods": len(coefficient_frame),
            "hac_maxlags": maxlags,
            "covariance_type": primary_cov,
            "intercept": True,
        },
    )


def run_portfolio_sort(
    frame: pd.DataFrame,
    model: ModelDesign,
    config: ExperimentConfig,
    *,
    date_column: str,
    data_fingerprint: str | None = None,
) -> ExperimentResult:
    """Run sequential turnover-then-IVOL equal-weight portfolio sorts."""
    dependent = model.dependent_variable.name
    primary = config.portfolio_primary_variable
    secondary = config.portfolio_secondary_variable
    available = {
        variable.name.casefold(): variable.name
        for variable in [
            *model.independent_variables,
            *model.control_variables,
        ]
    }
    try:
        primary = available[primary.casefold()]
        secondary = available[secondary.casefold()]
    except KeyError as exc:
        raise ExperimentEngineError(
            "Portfolio sort model must include configured variables: "
            f"{config.portfolio_primary_variable}, "
            f"{config.portfolio_secondary_variable}"
        ) from exc
    sample, dropped = _complete_sample(
        frame, dependent, [primary, secondary], [date_column]
    )
    sample[date_column] = pd.to_datetime(sample[date_column], errors="coerce")
    if sample[date_column].isna().any():
        raise ExperimentEngineError("Portfolio-sort dates contain invalid values")

    groups = config.portfolio_groups
    period_cells: list[pd.DataFrame] = []
    skipped_periods = 0
    used_observations = 0
    for period_date, period in sample.groupby(date_column, sort=True):
        if len(period) < groups * groups:
            skipped_periods += 1
            continue
        assigned = period.copy()
        assigned["primary_group"] = pd.qcut(
            assigned[primary].rank(method="first"),
            groups,
            labels=range(1, groups + 1),
        ).astype(int)
        secondary_groups = []
        valid_period = True
        for _, primary_subset in assigned.groupby("primary_group", sort=True):
            if len(primary_subset) < groups:
                valid_period = False
                break
            labels = pd.qcut(
                primary_subset[secondary].rank(method="first"),
                groups,
                labels=range(1, groups + 1),
            ).astype(int)
            secondary_groups.append(pd.Series(labels, index=primary_subset.index))
        if not valid_period:
            skipped_periods += 1
            continue
        assigned["secondary_group"] = pd.concat(secondary_groups).sort_index()
        cells = (
            assigned.groupby(["primary_group", "secondary_group"], observed=True)[
                dependent
            ]
            .agg(["mean", "size"])
            .reset_index()
        )
        if len(cells) != groups * groups:
            skipped_periods += 1
            continue
        cells[date_column] = period_date
        period_cells.append(cells)
        used_observations += len(assigned)

    if len(period_cells) < config.minimum_fama_macbeth_periods:
        raise ExperimentEngineError(
            "Too few complete periods for sequential portfolio-sort inference"
        )
    cell_frame = pd.concat(period_cells, ignore_index=True)
    maxlags = min(config.hac_maxlags, len(period_cells) - 1)
    statistics: list[StatisticalResult] = []
    alternative_flags: dict[str, bool] = {}
    for primary_group in range(1, groups + 1):
        group_cells = cell_frame.loc[
            cell_frame["primary_group"] == primary_group
        ].pivot(index=date_column, columns="secondary_group", values="mean")
        spread = group_cells[groups] - group_cells[1]
        constant = np.ones((len(spread), 1))
        primary_fit = sm.OLS(spread.to_numpy(float), constant).fit(
            cov_type="HAC", cov_kwds={"maxlags": maxlags}, use_t=True
        )
        alternative = sm.OLS(spread.to_numpy(float), constant).fit(use_t=True)
        interval = primary_fit.conf_int(alpha=config.significance_level)[0]
        p_value = float(primary_fit.pvalues[0])
        variable = f"T{primary_group}_high_minus_low_{secondary}"
        statistics.append(
            StatisticalResult(
                variable=variable,
                coefficient=float(primary_fit.params[0]),
                standard_error=float(primary_fit.bse[0]),
                t_stat=float(primary_fit.tvalues[0]),
                p_value=p_value,
                confidence_interval=(float(interval[0]), float(interval[1])),
                significant=bool(p_value < config.significance_level),
            )
        )
        alternative_flags[variable] = bool(
            alternative.pvalues[0] < config.significance_level
        )

    portfolio_results = [
        PortfolioCellResult(
            primary_group=int(str(primary_group)),
            secondary_group=int(str(secondary_group)),
            mean_return=float(group["mean"].mean()),
            observations=int(group["size"].sum()),
        )
        for (primary_group, secondary_group), group in cell_frame.groupby(
            ["primary_group", "secondary_group"], observed=True
        )
    ]
    stability = all(
        result.significant == alternative_flags[result.variable]
        for result in statistics
    )
    warnings = []
    if dropped:
        warnings.append(f"Dropped {dropped} rows with missing sort variables.")
    if skipped_periods:
        warnings.append(
            f"Skipped {skipped_periods} periods without all sequential portfolios."
        )
    highest = statistics[-1]
    return ExperimentResult(
        method=(
            f"Sequential {groups}x{groups} equal-weight portfolio sort: "
            f"{primary} then {secondary}"
        ),
        estimator=Estimator.PORTFOLIO_SORT,
        sample_size=used_observations,
        significance_level=config.significance_level,
        model_metrics=ModelMetrics(observations=used_observations),
        statistical_results=statistics,
        robustness_checks=[
            RobustnessCheck(
                name="Portfolio-spread covariance sensitivity",
                method="Compare HAC and nonrobust high-minus-low inference",
                result=(
                    "Significance classifications are stable"
                    if stability
                    else "At least one significance classification changes"
                ),
                passed=stability,
            )
        ],
        warnings=warnings,
        conclusion=(
            f"Highest-{primary} high-minus-low {secondary} spread is "
            f"{highest.coefficient:.6g} (p={highest.p_value:.4g})."
        ),
        data_fingerprint=data_fingerprint,
        parameters={
            "periods": len(period_cells),
            "groups": groups,
            "primary_sort": primary,
            "secondary_sort": secondary,
            "weighting": "equal",
            "hac_maxlags": maxlags,
        },
        portfolio_results=portfolio_results,
    )


def run_backtest(*args, **kwargs) -> ExperimentResult:
    """Reserved Round 4 route; implementation is intentionally explicit."""
    raise UnsupportedEstimatorError(
        "Estimator 'backtest' is not implemented in Round 4"
    )


def run_experiment(
    frame: pd.DataFrame,
    model: ModelDesign,
    config: ExperimentConfig,
    *,
    date_column: str,
    data_fingerprint: str | None = None,
) -> ExperimentResult:
    """Route an enumerated estimator to its exact implementation."""
    if model.estimator == Estimator.OLS:
        return run_ols(frame, model, config, data_fingerprint=data_fingerprint)
    if model.estimator == Estimator.FAMA_MACBETH:
        return run_fama_macbeth(
            frame,
            model,
            config,
            date_column=date_column,
            data_fingerprint=data_fingerprint,
        )
    if model.estimator == Estimator.PORTFOLIO_SORT:
        return run_portfolio_sort(
            frame,
            model,
            config,
            date_column=date_column,
            data_fingerprint=data_fingerprint,
        )
    if model.estimator == Estimator.BACKTEST:
        return run_backtest()
    raise UnsupportedEstimatorError(f"Unknown estimator: {model.estimator.value!r}")
