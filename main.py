"""QuantResearchAgent command-line entry point."""

import argparse
from dataclasses import replace
from datetime import date
from pathlib import Path

from graph.intent_router import route_request
from graph.workflow import build_workflow
from logging_config import configure_logging
from production import run_research
from schemas.enums import DataFrequency, TaskType
from schemas.platform import ResearchRequest
from tools.financial_data import LocalDataConfig
from tools.report_templates import resolve_report_template


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the Financial Research & Advisory Agent platform"
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Use the configured paid LLM and execute the workflow",
    )
    parser.add_argument("--question", help="Research question for a live run")
    parser.add_argument(
        "--task-type",
        choices=[task_type.value for task_type in TaskType],
        help="Preview a platform route; quant_research is the current live workflow",
    )
    parser.add_argument("--company", action="append", default=[])
    parser.add_argument("--industry", action="append", default=[])
    parser.add_argument("--security", action="append", default=[])
    parser.add_argument("--as-of-date", type=date.fromisoformat, default=date.today())
    parser.add_argument("--data", type=Path, help="CSV or Parquet research dataset")
    parser.add_argument(
        "--revision-data",
        type=Path,
        action="append",
        default=[],
        help=(
            "Larger compatible dataset used on a Data Revision; repeat this option "
            "for staged expansion"
        ),
    )
    parser.add_argument("--date-column", default="date")
    parser.add_argument("--target-date-column", default="target_date")
    parser.add_argument("--entity-column", default="stock_id")
    parser.add_argument(
        "--frequency",
        choices=[frequency.value for frequency in DataFrequency],
        default=DataFrequency.MONTHLY.value,
    )
    parser.add_argument("--universe", default="User-provided research universe")
    parser.add_argument("--outlier-handling", default="Not specified")
    parser.add_argument("--survivorship-policy")
    parser.add_argument("--max-revisions", type=int, default=3)
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("reports/live_research_report.md"),
    )
    parser.add_argument(
        "--experiment-artifacts",
        type=Path,
        default=Path("reports/experiments"),
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    """Compile the graph or explicitly execute its paid production wiring."""
    configure_logging()
    args = _parser().parse_args(argv)
    if not args.live:
        if args.task_type:
            request = ResearchRequest(
                task_type=TaskType(args.task_type),
                question=args.question or f"Route preview for {args.task_type}",
                companies=args.company,
                industries=args.industry,
                securities=args.security,
                as_of_date=args.as_of_date,
            )
            selection = route_request(request)
            print(f"Task type: {selection.task_type.value}")
            print(f"Workflow: {selection.workflow_name}")
            print(
                "Analysis methods: "
                + ", ".join(method.value for method in selection.analysis_methods)
            )
            print(f"Report template: {resolve_report_template(selection)}")
            return
        workflow = build_workflow()
        print(
            "Financial Research & Advisory platform workflow initialized: "
            f"{type(workflow).__name__}"
        )
        print("Current live workflow: quant_research (seven-node graph)")
        print("Use --task-type to preview other routes without calling an LLM.")
        print("Use --live with --question and --data for live quant research.")
        return
    if args.task_type and args.task_type != TaskType.QUANT_RESEARCH.value:
        _parser().error("--live currently supports only --task-type quant_research")
    if not args.question or args.data is None:
        _parser().error("--live requires both --question and --data")

    data_config = LocalDataConfig(
        path=args.data,
        date_column=args.date_column,
        target_date_column=args.target_date_column,
        entity_column=args.entity_column,
        frequency=DataFrequency(args.frequency),
        universe=args.universe,
        outlier_handling=args.outlier_handling,
        survivorship_policy=args.survivorship_policy,
    )
    result = run_research(
        args.question,
        data_config,
        max_revisions=args.max_revisions,
        revision_data_configs=tuple(
            replace(
                data_config,
                path=path,
                universe=f"{args.universe} (data revision {index})",
            )
            for index, path in enumerate(args.revision_data, start=1)
        ),
        report_path=args.report,
        experiment_artifact_directory=args.experiment_artifacts,
    )
    report = result["final_report"]
    print(f"Research workflow completed: decision={report.review_decision.value}")
    print(f"Report: {result.get('report_markdown_path', args.report)}")


if __name__ == "__main__":
    main()
