"""Download resumable BaoStock returns for the historical P9709 universe."""

from __future__ import annotations

import argparse
import logging
from datetime import date
from pathlib import Path

import pandas as pd

from data_sources.baostock_returns import (
    BaoStockReturnConfig,
    build_baostock_return_cache,
)
from data_sources.thesis_v2 import is_p9709_stock, normalize_stock_code


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--universe",
        type=Path,
        default=Path("data/baostock/universe/a_share_month_end_2e3726a66e39.parquet"),
    )
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=Path("data/baostock/monthly_returns_v2"),
    )
    parser.add_argument("--start", type=date.fromisoformat, default=date(2010, 1, 1))
    parser.add_argument("--end", type=date.fromisoformat, default=date(2025, 12, 31))
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--frequency", choices=("d", "m"), default="m")
    parser.add_argument("--batch-size", type=int, default=200)
    parser.add_argument("--batch-pause-seconds", type=float, default=3.0)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--refresh", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    universe = pd.read_parquet(args.universe, columns=["stock_id"])
    codes = sorted(
        {
            str(code).casefold()
            for code in universe["stock_id"]
            if is_p9709_stock(normalize_stock_code(code))
        }
    )
    if args.limit is not None:
        codes = codes[: args.limit]
    result = build_baostock_return_cache(
        BaoStockReturnConfig(
            codes=tuple(codes),
            start_date=args.start,
            end_date=args.end,
            output_directory=args.output_directory,
            workers=args.workers,
            frequency=args.frequency,
            refresh=args.refresh,
            batch_size=args.batch_size,
            batch_pause_seconds=args.batch_pause_seconds,
        )
    )
    print(f"stock_directory={result.stock_directory.resolve()}")
    print(f"manifest={result.manifest_path.resolve()}")
    print(
        f"codes={result.completed_codes:,}/{result.requested_codes:,}; "
        f"rows={result.rows:,}; cache_hits={result.cache_hits:,}; "
        f"empty={result.empty_codes:,}; failed={result.failed_codes:,}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
