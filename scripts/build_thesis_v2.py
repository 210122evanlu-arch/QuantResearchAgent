"""Command-line builder for the corrected thesis replication dataset."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from data_sources.thesis_v2 import (
    ThesisV2Config,
    build_thesis_v2_dataset,
    save_thesis_v2_dataset,
)


def _paths(pattern: str) -> tuple[Path, ...]:
    base = Path.home()
    return tuple(sorted(base.glob(pattern)))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--daily-directory",
        type=Path,
        default=Path.home() / "A_share_daily_data",
    )
    parser.add_argument(
        "--factor-path",
        type=Path,
        default=Path(
            "data/licensed/csmar/five_factor_daily_123315679/ff5_p9709_2x3_float.parquet"
        ),
    )
    parser.add_argument(
        "--turnover-path",
        type=Path,
        default=Path("D:/低波动率异象/LIQ_TOVER_M.xlsx"),
    )
    parser.add_argument(
        "--universe-path",
        type=Path,
        default=Path("data/baostock/universe/a_share_month_end_2e3726a66e39.parquet"),
    )
    parser.add_argument("--output-directory", type=Path, default=Path("data/prepared"))
    parser.add_argument("--baostock-monthly-return-directory", type=Path)
    parser.add_argument(
        "--risk-free-path",
        type=Path,
        help="Daily decimal RF proxy; enables the v4 excess-return specification",
    )
    parser.add_argument(
        "--industry-snapshot-directory",
        type=Path,
        help="Point-in-time BaoStock industry snapshot Parquets",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    market_cap_paths = _paths("TRD_Dalyr*.csv")
    pb_paths = _paths("STK_MKT_DALYR*.csv")
    if not market_cap_paths or not pb_paths:
        raise FileNotFoundError(
            "CSMAR market-cap or PB CSV files were not found in the user home directory"
        )
    config = ThesisV2Config(
        daily_directory=args.daily_directory,
        factor_path=args.factor_path,
        market_cap_paths=market_cap_paths,
        pb_paths=pb_paths,
        turnover_path=args.turnover_path,
        universe_path=args.universe_path,
        cache_directory=args.output_directory,
        baostock_monthly_return_directory=args.baostock_monthly_return_directory,
        risk_free_path=args.risk_free_path,
        industry_snapshot_directory=args.industry_snapshot_directory,
    )
    panel, audit = build_thesis_v2_dataset(config)
    if args.risk_free_path is not None and args.industry_snapshot_directory is not None:
        stem = "molly_regression_final_v5_rf_industry_baostock"
    elif args.risk_free_path is not None:
        stem = "molly_regression_final_v4_rf_baostock"
    elif args.baostock_monthly_return_directory is not None:
        stem = "molly_regression_final_v3_baostock_target"
    else:
        stem = "molly_regression_final_v2"
    panel_path, audit_path = save_thesis_v2_dataset(
        panel, audit, args.output_directory, stem=stem
    )
    print(f"panel={panel_path.resolve()}")
    print(f"audit={audit_path.resolve()}")
    print(f"rows={len(panel):,}; stocks={panel['stock_id'].nunique():,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
