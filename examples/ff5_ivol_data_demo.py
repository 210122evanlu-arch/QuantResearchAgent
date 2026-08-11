"""Build a five-factor IVOL panel from licensed/local daily inputs."""

import argparse
from pathlib import Path

from data_sources.fama_french import (
    CsmarFactorDataConfig,
    FactorDataConfig,
    load_csmar_five_factor_data,
    load_five_factor_data,
    prepare_five_factor_ivol_panel,
)
from tools.financial_data import load_financial_data


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build a strict FF5 IVOL panel")
    parser.add_argument("--stocks", required=True, type=Path)
    parser.add_argument("--factors", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--factor-percent", action="store_true")
    parser.add_argument(
        "--factor-provider", choices=("generic", "csmar"), default="generic"
    )
    parser.add_argument("--market-type", default="P9709")
    parser.add_argument("--portfolios", type=int, default=1)
    parser.add_argument(
        "--weighting",
        choices=("float_market_cap", "total_market_cap"),
        default="float_market_cap",
    )
    parser.add_argument("--risk-free", type=Path)
    parser.add_argument("--risk-free-percent", action="store_true")
    parser.add_argument("--reproduce-original-workflow", action="store_true")
    parser.add_argument("--minimum-days", type=int, default=15)
    args = parser.parse_args(argv)

    if args.factor_provider == "csmar":
        factor_data = load_csmar_five_factor_data(
            CsmarFactorDataConfig(
                path=args.factors,
                market_type=args.market_type,
                portfolios=args.portfolios,
                weighting=args.weighting,
                risk_free_path=args.risk_free,
                risk_free_values_in_percent=args.risk_free_percent,
                reproduce_original_workflow=args.reproduce_original_workflow,
            )
        )
    else:
        factor_data = load_five_factor_data(
            FactorDataConfig(path=args.factors, values_in_percent=args.factor_percent)
        )
    panel = prepare_five_factor_ivol_panel(
        load_financial_data(args.stocks),
        factor_data,
        minimum_daily_observations=args.minimum_days,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    panel.to_parquet(args.output, index=False)
    print(
        "Five-factor IVOL panel ready:",
        f"rows={len(panel)}",
        f"factor_fingerprint={factor_data.fingerprint}",
        f"return_basis={factor_data.metadata.get('return_basis')}",
    )
    print(f"Panel: {args.output.resolve()}")


if __name__ == "__main__":
    main()
