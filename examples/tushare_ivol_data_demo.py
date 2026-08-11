"""Download a selected-stock Tushare sample and prepare an IVOL panel."""

import argparse
from datetime import date

from config import TushareSettings
from data_sources.tushare import TushareBuildConfig, TushareIVOLDataBuilder


def _date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Use YYYY-MM-DD") from exc


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build a cached Tushare IVOL panel")
    parser.add_argument(
        "--codes",
        required=True,
        help="Comma-separated Tushare codes, for example 000001.SZ,600000.SH",
    )
    parser.add_argument("--start", required=True, type=_date)
    parser.add_argument("--end", required=True, type=_date)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args(argv)

    codes = tuple(
        code.strip().upper() for code in args.codes.split(",") if code.strip()
    )
    result = TushareIVOLDataBuilder(TushareSettings.from_env()).build(
        TushareBuildConfig(
            ts_codes=codes,
            start_date=args.start,
            end_date=args.end,
            refresh=args.refresh,
        )
    )
    print(
        "Tushare IVOL panel ready:",
        f"raw_rows={result.raw_rows}",
        f"panel_rows={result.panel_rows}",
        f"cache_hit={result.cache_hit}",
    )
    print(f"Panel: {result.panel_path.resolve()}")
    print(f"Manifest: {result.manifest_path.resolve()}")


if __name__ == "__main__":
    main()
