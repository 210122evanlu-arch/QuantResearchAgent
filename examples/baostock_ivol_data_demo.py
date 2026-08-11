"""Download a free BaoStock sample and prepare an IVOL panel."""

import argparse
from datetime import date

from config import BaoStockSettings
from data_sources.baostock import BaoStockBuildConfig, BaoStockIVOLDataBuilder


def _date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Use YYYY-MM-DD") from exc


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build a cached BaoStock IVOL panel")
    parser.add_argument(
        "--codes",
        required=True,
        help="Comma-separated BaoStock codes, for example sz.000001,sh.600000",
    )
    parser.add_argument("--start", required=True, type=_date)
    parser.add_argument("--end", required=True, type=_date)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args(argv)
    codes = tuple(
        code.strip().lower() for code in args.codes.split(",") if code.strip()
    )
    result = BaoStockIVOLDataBuilder(BaoStockSettings.from_env()).build(
        BaoStockBuildConfig(
            codes=codes,
            start_date=args.start,
            end_date=args.end,
            refresh=args.refresh,
        )
    )
    print(
        "BaoStock IVOL panel ready:",
        f"raw_rows={result.raw_rows}",
        f"panel_rows={result.panel_rows}",
        f"cache_hit={result.cache_hit}",
    )
    print(f"Panel: {result.panel_path.resolve()}")
    print(f"Manifest: {result.manifest_path.resolve()}")


if __name__ == "__main__":
    main()
