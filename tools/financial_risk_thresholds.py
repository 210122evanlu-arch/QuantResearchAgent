"""Auditable industry threshold registry for financial-risk screening."""

from schemas.enums import IndustryProfile
from schemas.financial_risk_thresholds import FinancialRiskThresholds


def _profile(
    industry: IndustryProfile,
    **updates: float,
) -> FinancialRiskThresholds:
    values: dict[str, float | str | IndustryProfile] = {
        "profile": industry,
        "version": "industry-thresholds-1.0",
        "cash_conversion_min": 0.80,
        "accrual_ratio_max": 0.10,
        "receivable_growth_gap_max": 0.15,
        "inventory_growth_gap_max": 0.15,
        "gross_margin_deviation_max": 0.05,
        "non_recurring_profit_ratio_max": 0.30,
        "current_ratio_min": 1.00,
        "net_debt_to_cfo_max": 3.00,
        "debt_to_assets_max": 0.70,
        "interest_coverage_min": 2.00,
        "roe_decline_max": 0.05,
        "net_margin_decline_max": 0.05,
        "receivable_days_growth_max": 0.30,
        "inventory_days_growth_max": 0.30,
        "asset_turnover_decline_max": 0.20,
        "impairment_to_assets_max": 0.03,
        "goodwill_to_assets_max": 0.20,
        "related_party_ratio_max": 0.10,
        "customer_concentration_max": 0.30,
        "supplier_concentration_max": 0.30,
        "rd_capitalization_ratio_max": 0.50,
    }
    values.update(updates)
    return FinancialRiskThresholds.model_validate(values)


INDUSTRY_THRESHOLDS = {
    IndustryProfile.GENERAL: _profile(IndustryProfile.GENERAL),
    IndustryProfile.MANUFACTURING: _profile(
        IndustryProfile.MANUFACTURING,
        inventory_growth_gap_max=0.20,
        current_ratio_min=0.90,
        net_debt_to_cfo_max=3.50,
        inventory_days_growth_max=0.35,
        supplier_concentration_max=0.35,
    ),
    IndustryProfile.CONSUMER: _profile(
        IndustryProfile.CONSUMER,
        cash_conversion_min=0.90,
        inventory_growth_gap_max=0.12,
        gross_margin_deviation_max=0.07,
        inventory_days_growth_max=0.20,
        customer_concentration_max=0.35,
    ),
    IndustryProfile.TECHNOLOGY: _profile(
        IndustryProfile.TECHNOLOGY,
        current_ratio_min=1.20,
        gross_margin_deviation_max=0.10,
        goodwill_to_assets_max=0.25,
        rd_capitalization_ratio_max=0.40,
        customer_concentration_max=0.40,
    ),
    IndustryProfile.REAL_ESTATE: _profile(
        IndustryProfile.REAL_ESTATE,
        cash_conversion_min=0.60,
        inventory_growth_gap_max=0.30,
        current_ratio_min=1.10,
        net_debt_to_cfo_max=5.00,
        debt_to_assets_max=0.80,
        inventory_days_growth_max=0.50,
    ),
}


def get_financial_risk_thresholds(
    industry: IndustryProfile,
) -> FinancialRiskThresholds:
    """Return an immutable validated profile selected by code, not an LLM."""
    return INDUSTRY_THRESHOLDS[industry].model_copy(deep=True)
