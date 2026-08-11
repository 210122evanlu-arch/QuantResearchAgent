"""Download semiannual point-in-time BaoStock industry snapshots."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from data_sources.baostock_industry import (
    BaoStockIndustryConfig,
    build_baostock_industry_cache,
)


def _semiannual_dates(start_year: int, end_year: int) -> tuple[date, ...]:
    return tuple(
        date(year, month, 28)
        for year in range(start_year, end_year + 1)
        for month in (1, 7)
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-year", type=int, default=2010)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=Path("data/baostock/industry_semiannual"),
    )
    parser.add_argument("--refresh", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.start_year > args.end_year:
        raise ValueError("start_year must not exceed end_year")
    result = build_baostock_industry_cache(
        BaoStockIndustryConfig(
            snapshot_dates=_semiannual_dates(args.start_year, args.end_year),
            output_directory=args.output_directory,
            refresh=args.refresh,
        )
    )
    print(f"snapshots={result.snapshot_directory.resolve()}")
    print(f"manifest={result.manifest_path.resolve()}")
    print(
        f"completed={result.completed_snapshots}/{result.requested_snapshots}; "
        f"rows={result.rows:,}; cache_hits={result.cache_hits}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
