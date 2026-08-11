"""Discounted cash-flow inputs, outputs, and sensitivity contracts."""

from pydantic import BaseModel, Field, model_validator


class CashFlowProjection(BaseModel):
    year: int = Field(ge=1)
    free_cash_flow: float


class DCFInput(BaseModel):
    currency: str = Field(min_length=1)
    projections: list[CashFlowProjection] = Field(min_length=2)
    discount_rate: float = Field(gt=0, lt=1)
    terminal_growth_rate: float = Field(gt=-1, lt=1)
    net_debt: float
    shares_outstanding: float = Field(gt=0)

    @model_validator(mode="after")
    def validate_terminal_value(self) -> "DCFInput":
        if self.discount_rate <= self.terminal_growth_rate:
            raise ValueError("discount_rate must exceed terminal_growth_rate")
        years = [item.year for item in self.projections]
        if years != sorted(set(years)):
            raise ValueError("projection years must be unique and increasing")
        return self


class DCFSensitivityConfig(BaseModel):
    discount_rate_step: float = Field(default=0.01, gt=0, lt=0.1)
    terminal_growth_step: float = Field(default=0.005, gt=0, lt=0.1)
    steps_each_side: int = Field(default=2, ge=1, le=5)


class SensitivityCell(BaseModel):
    discount_rate: float
    terminal_growth_rate: float
    value_per_share: float


class DCFResult(BaseModel):
    currency: str
    enterprise_value: float
    equity_value: float
    value_per_share: float
    present_value_forecast: float
    present_value_terminal: float
    terminal_value_share: float = Field(ge=0)
    sensitivity: list[SensitivityCell] = Field(min_length=1)
    warnings: list[str] = Field(default_factory=list)
