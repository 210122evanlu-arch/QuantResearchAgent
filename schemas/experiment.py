"""Quantitative experiment outputs and statistical diagnostics."""

from pydantic import BaseModel, Field, model_validator

from schemas.enums import Estimator


class ModelMetrics(BaseModel):
    r_squared: float | None = None
    adjusted_r_squared: float | None = None
    observations: int = Field(ge=0)
    rmse: float | None = Field(default=None, ge=0)
    information_coefficient: float | None = None


class StatisticalResult(BaseModel):
    variable: str
    coefficient: float
    standard_error: float | None = None
    t_stat: float | None = None
    p_value: float | None = Field(default=None, ge=0, le=1)
    confidence_interval: tuple[float, float] | None = None
    significant: bool


class RobustnessCheck(BaseModel):
    name: str
    method: str
    result: str
    passed: bool


class PortfolioCellResult(BaseModel):
    primary_group: int = Field(ge=1)
    secondary_group: int = Field(ge=1)
    mean_return: float
    observations: int = Field(ge=0)


class ExperimentResult(BaseModel):
    method: str
    estimator: Estimator | None = None
    sample_size: int = Field(ge=0)
    significance_level: float = Field(default=0.05, gt=0, lt=1)
    model_metrics: ModelMetrics
    statistical_results: list[StatisticalResult]
    robustness_checks: list[RobustnessCheck]
    warnings: list[str]
    conclusion: str
    data_fingerprint: str | None = None
    parameters: dict[str, str | int | float | bool] = Field(default_factory=dict)
    portfolio_results: list[PortfolioCellResult] = Field(default_factory=list)
    artifact_path: str | None = None

    @model_validator(mode="after")
    def validate_significance_flags(self) -> "ExperimentResult":
        if self.sample_size != self.model_metrics.observations:
            raise ValueError("sample_size must match model_metrics.observations")
        for result in self.statistical_results:
            if result.p_value is not None:
                expected = result.p_value < self.significance_level
                if result.significant != expected:
                    raise ValueError(
                        f"significant flag for {result.variable!r} does not match "
                        "p_value and significance_level"
                    )
            if (
                result.confidence_interval is not None
                and result.confidence_interval[0] > result.confidence_interval[1]
            ):
                raise ValueError(
                    f"confidence interval for {result.variable!r} is reversed"
                )
        return self
