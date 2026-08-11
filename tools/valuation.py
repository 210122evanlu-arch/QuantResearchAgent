"""Deterministic discounted cash-flow and sensitivity calculations."""

from schemas.valuation import (
    DCFInput,
    DCFResult,
    DCFSensitivityConfig,
    SensitivityCell,
)


def _value(
    inputs: DCFInput, discount_rate: float, growth_rate: float
) -> tuple[float, float, float]:
    if discount_rate <= growth_rate:
        raise ValueError("discount_rate must exceed terminal growth in every scenario")
    forecast = sum(
        item.free_cash_flow / (1 + discount_rate) ** item.year
        for item in inputs.projections
    )
    last = inputs.projections[-1]
    terminal = last.free_cash_flow * (1 + growth_rate) / (discount_rate - growth_rate)
    terminal_present = terminal / (1 + discount_rate) ** last.year
    enterprise = forecast + terminal_present
    return forecast, terminal_present, enterprise


def run_dcf(
    inputs: DCFInput,
    sensitivity: DCFSensitivityConfig | None = None,
) -> DCFResult:
    config = sensitivity or DCFSensitivityConfig()
    forecast, terminal, enterprise = _value(
        inputs, inputs.discount_rate, inputs.terminal_growth_rate
    )
    equity = enterprise - inputs.net_debt
    cells: list[SensitivityCell] = []
    invalid_scenarios = 0
    offsets = range(-config.steps_each_side, config.steps_each_side + 1)
    for discount_offset in offsets:
        discount_rate = (
            inputs.discount_rate + discount_offset * config.discount_rate_step
        )
        for growth_offset in offsets:
            growth_rate = (
                inputs.terminal_growth_rate
                + growth_offset * config.terminal_growth_step
            )
            if discount_rate <= growth_rate or discount_rate <= 0:
                invalid_scenarios += 1
                continue
            _, _, scenario_enterprise = _value(inputs, discount_rate, growth_rate)
            cells.append(
                SensitivityCell(
                    discount_rate=discount_rate,
                    terminal_growth_rate=growth_rate,
                    value_per_share=(scenario_enterprise - inputs.net_debt)
                    / inputs.shares_outstanding,
                )
            )
    warnings = []
    terminal_share = terminal / enterprise if enterprise else 0.0
    if terminal_share > 0.75:
        warnings.append("Terminal value exceeds 75% of enterprise value.")
    if equity <= 0:
        warnings.append("DCF produces non-positive equity value.")
    if invalid_scenarios:
        warnings.append(f"Skipped {invalid_scenarios} invalid sensitivity scenarios.")
    return DCFResult(
        currency=inputs.currency,
        enterprise_value=enterprise,
        equity_value=equity,
        value_per_share=equity / inputs.shares_outstanding,
        present_value_forecast=forecast,
        present_value_terminal=terminal,
        terminal_value_share=terminal_share,
        sensitivity=cells,
        warnings=warnings,
    )
