"""Versioned industry calibration for explainable financial-risk rules."""

from pydantic import BaseModel, Field

from schemas.enums import IndustryProfile


class FinancialRiskThresholds(BaseModel):
    profile: IndustryProfile
    version: str = Field(min_length=1)
    cash_conversion_min: float
    accrual_ratio_max: float
    receivable_growth_gap_max: float
    inventory_growth_gap_max: float
    gross_margin_deviation_max: float
    non_recurring_profit_ratio_max: float
    current_ratio_min: float = Field(ge=0)
    net_debt_to_cfo_max: float
    debt_to_assets_max: float = Field(ge=0)
    interest_coverage_min: float
    roe_decline_max: float = Field(ge=0)
    net_margin_decline_max: float = Field(ge=0)
    receivable_days_growth_max: float = Field(ge=0)
    inventory_days_growth_max: float = Field(ge=0)
    asset_turnover_decline_max: float = Field(ge=0)
    impairment_to_assets_max: float = Field(ge=0)
    goodwill_to_assets_max: float = Field(ge=0)
    related_party_ratio_max: float = Field(ge=0)
    customer_concentration_max: float = Field(ge=0, le=1)
    supplier_concentration_max: float = Field(ge=0, le=1)
    rd_capitalization_ratio_max: float = Field(ge=0, le=1)
