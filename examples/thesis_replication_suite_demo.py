"""Run locked thesis specifications on a prepared approximation panel."""

import argparse
import json
from pathlib import Path

from tools.financial_data import load_financial_data
from tools.thesis_replication import run_thesis_replication_suite


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run locked IVOL thesis models")
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)

    results = run_thesis_replication_suite(load_financial_data(args.data))
    payload = {name: result.model_dump(mode="json") for name, result in results.items()}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Thesis replication suite: {args.output.resolve()}")


if __name__ == "__main__":
    main()
