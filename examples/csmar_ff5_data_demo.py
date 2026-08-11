"""Normalize a licensed CSMAR daily five-factor export for local research."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from data_sources.fama_french import (
    CsmarFactorDataConfig,
    load_csmar_five_factor_data,
)
from tools.financial_data import compute_dataset_fingerprint


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Normalize a CSMAR daily FF5 export")
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
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
    args = parser.parse_args(argv)

    dataset = load_csmar_five_factor_data(
        CsmarFactorDataConfig(
            path=args.source,
            market_type=args.market_type,
            portfolios=args.portfolios,
            weighting=args.weighting,
            risk_free_path=args.risk_free,
            risk_free_values_in_percent=args.risk_free_percent,
            reproduce_original_workflow=args.reproduce_original_workflow,
        )
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    dataset.frame.to_parquet(args.output, index=False)
    manifest_path = args.output.with_suffix(".json")
    manifest = {
        "provider": "CSMAR",
        "source_path": str(args.source.resolve()),
        "source_fingerprint": compute_dataset_fingerprint(args.source),
        "normalized_fingerprint": compute_dataset_fingerprint(args.output),
        "configured_factor_fingerprint": dataset.fingerprint,
        "rows": len(dataset.frame),
        "start_date": dataset.frame["date"].min().date().isoformat(),
        "end_date": dataset.frame["date"].max().date().isoformat(),
        "metadata": dataset.metadata,
        "created_at_utc": datetime.now(UTC).isoformat(),
        "redistribution": "prohibited; local licensed use only",
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        "CSMAR five-factor series ready:",
        f"rows={len(dataset.frame)}",
        f"range={manifest['start_date']}..{manifest['end_date']}",
        f"return_basis={dataset.metadata['return_basis']}",
    )
    print(f"Factors: {args.output.resolve()}")
    print(f"Manifest: {manifest_path.resolve()}")


if __name__ == "__main__":
    main()
