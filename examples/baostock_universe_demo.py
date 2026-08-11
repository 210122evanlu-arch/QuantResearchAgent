"""Build cached historical month-end A-share universe snapshots."""

import argparse
from datetime import date

from config import BaoStockSettings
from data_sources.baostock_universe import (
    BaoStockHistoricalUniverseBuilder,
    BaoStockUniverseConfig,
)


def _date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Use YYYY-MM-DD") from exc


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Build BaoStock historical A-share universe snapshots"
    )
    parser.add_argument("--start", required=True, type=_date)
    parser.add_argument("--end", required=True, type=_date)
    parser.add_argument("--exclude-beijing", action="store_true")
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args(argv)
    result = BaoStockHistoricalUniverseBuilder(BaoStockSettings.from_env()).build(
        BaoStockUniverseConfig(
            start_date=args.start,
            end_date=args.end,
            include_beijing=not args.exclude_beijing,
            refresh=args.refresh,
        )
    )
    print(
        "Historical A-share universe ready:",
        f"rows={result.rows}",
        f"securities={result.unique_securities}",
        f"months={result.monthly_snapshots}",
        f"cache_hit={result.cache_hit}",
    )
    print(f"Universe: {result.universe_path.resolve()}")
    print(f"Manifest: {result.manifest_path.resolve()}")


if __name__ == "__main__":
    main()
