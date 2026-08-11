"""Download the ChinaBond three-month government-yield risk-free proxy."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from data_sources.risk_free import (
    ChinaBondRiskFreeConfig,
    download_chinabond_risk_free,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--start-date", type=date.fromisoformat, default=date(2010, 1, 1)
    )
    parser.add_argument(
        "--end-date", type=date.fromisoformat, default=date(2025, 12, 31)
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/market/risk_free/chinabond_3m_daily.parquet"),
    )
    parser.add_argument("--annualization-days", type=int, default=252)
    parser.add_argument("--refresh", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = download_chinabond_risk_free(
        ChinaBondRiskFreeConfig(
            start_date=args.start_date,
            end_date=args.end_date,
            output_path=args.output,
            annualization_days=args.annualization_days,
            refresh=args.refresh,
        )
    )
    print(f"data={result.data_path.resolve()}")
    print(f"manifest={result.manifest_path.resolve()}")
    print(
        f"rows={result.rows:,}; period={result.start_date}..{result.end_date}; "
        f"cache_hit={result.cache_hit}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
