"""Deterministic market-regime scoring used by strategy workflows."""

from schemas.market_strategy import (
    MarketRegime,
    MarketRegimeAssessment,
    MarketSignalSnapshot,
)

SIGNAL_WEIGHTS = {
    "growth_momentum": 0.25,
    "liquidity_support": 0.25,
    "valuation_attractiveness": 0.20,
    "earnings_momentum": 0.15,
    "risk_appetite": 0.15,
}


def assess_market_regime(snapshot: MarketSignalSnapshot) -> MarketRegimeAssessment:
    """Map bounded signals to an auditable regime score and label."""
    contributions = {
        name: float(getattr(snapshot, name) * weight)
        for name, weight in SIGNAL_WEIGHTS.items()
    }
    score = sum(contributions.values())
    if score >= 0.35:
        regime = MarketRegime.RISK_ON
    elif score <= -0.35:
        regime = MarketRegime.DEFENSIVE
    elif abs(score) <= 0.10:
        regime = MarketRegime.BALANCED
    else:
        regime = MarketRegime.TRANSITION
    strongest = max(contributions, key=lambda name: abs(contributions[name]))
    return MarketRegimeAssessment(
        score=score,
        regime=regime,
        signal_contributions=contributions,
        rationale=(
            f"Weighted score={score:.3f}; the largest absolute contribution is "
            f"{strongest}={contributions[strongest]:.3f}."
        ),
    )
