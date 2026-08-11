"""Create a thesis-style feature panel from a monthly IVOL panel."""

import argparse
from pathlib import Path

from tools.financial_data import load_financial_data
from tools.thesis_ivol import prepare_thesis_ivol_features


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Add turnover-interaction and robustness features"
    )
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)

    panel = prepare_thesis_ivol_features(load_financial_data(args.input))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.suffix.casefold() == ".csv":
        panel.to_csv(args.output, index=False)
    else:
        panel.to_parquet(args.output, index=False)
    print(
        "Thesis-style IVOL features ready:",
        f"rows={len(panel)}",
        f"stocks={panel['stock_id'].nunique() if 'stock_id' in panel else 'unknown'}",
    )
    print(f"Panel: {args.output.resolve()}")


if __name__ == "__main__":
    main()
