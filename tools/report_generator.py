"""Deterministic Markdown rendering for traceable research reports."""

from pathlib import Path

from schemas.report import FinalReport


def _number(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.8g}"


def _cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_markdown_report(report: FinalReport) -> str:
    """Render only structured FinalReport values; no model call is involved."""
    status = (
        "APPROVED"
        if report.review_decision.value == "approved"
        else "NOT APPROVED — REVISION REQUIRED"
    )
    lines = [
        f"# {report.title}",
        "",
        f"> Committee status: **{status}**",
        "",
        "## Executive Summary",
        "",
        report.executive_summary,
        "",
        "## Research Background",
        "",
        report.research_background,
        "",
        "## Literature References",
        "",
        "| Year | Paper | Authors | Source | DOI / URL |",
        "| ---: | --- | --- | --- | --- |",
    ]
    for paper in report.references:
        locator = paper.doi_or_url or "Full-text verification pending"
        lines.append(
            "| "
            + " | ".join(
                [
                    str(paper.year),
                    _cell(paper.title),
                    _cell(", ".join(paper.authors)),
                    _cell(paper.source),
                    _cell(locator),
                ]
            )
            + " |"
        )

    lines.extend(["", "## Hypotheses", ""])
    lines.extend(f"- {hypothesis}" for hypothesis in report.hypotheses)
    lines.extend(
        [
            "",
            "## Methodology",
            "",
            report.methodology,
            "",
            "| Field | Verified value |",
            "| --- | --- |",
            f"| Model | {_cell(report.model_name)} |",
            f"| Formula | `{_cell(report.formula)}` |",
            f"| Estimator | `{report.estimator.value}` |",
            f"| Experiment method | {_cell(report.experiment_method)} |",
            "",
            "## Data",
            "",
            report.data_description,
            "",
            "| Metric | Verified value |",
            "| --- | ---: |",
            f"| Prepared rows | {report.data_sample_size} |",
            f"| Estimated rows | {report.experiment_sample_size} |",
            f"| Data fingerprint | `{report.data_fingerprint}` |",
            f"| Prepared-data fingerprint | `{report.prepared_data_fingerprint or 'N/A'}` |",
            f"| Experiment-data fingerprint | `{report.experiment_data_fingerprint or 'N/A'}` |",
            "",
            "## Experiment Results",
            "",
            "| Variable | Coefficient | Std. Error | t-stat | p-value | 95% CI | Significant |",
            "| --- | ---: | ---: | ---: | ---: | --- | :---: |",
        ]
    )
    for result in report.statistical_findings:
        interval = (
            "N/A"
            if result.confidence_interval is None
            else (
                f"[{_number(result.confidence_interval[0])}, "
                f"{_number(result.confidence_interval[1])}]"
            )
        )
        lines.append(
            "| "
            + " | ".join(
                [
                    _cell(result.variable),
                    _number(result.coefficient),
                    _number(result.standard_error),
                    _number(result.t_stat),
                    _number(result.p_value),
                    interval,
                    "Yes" if result.significant else "No",
                ]
            )
            + " |"
        )

    if report.portfolio_results:
        primary_groups = sorted(
            {cell.primary_group for cell in report.portfolio_results}
        )
        secondary_groups = sorted(
            {cell.secondary_group for cell in report.portfolio_results}
        )
        cells = {
            (cell.primary_group, cell.secondary_group): cell.mean_return
            for cell in report.portfolio_results
        }
        spreads = {
            group: cells[(group, secondary_groups[-1])]
            - cells[(group, secondary_groups[0])]
            for group in primary_groups
        }
        lines.extend(
            [
                "",
                "### Sequential Portfolio Returns",
                "",
                "| Turnover group | "
                + " | ".join(f"IVOL {group}" for group in secondary_groups)
                + " | High-Low |",
                "| --- | " + " | ".join("---:" for _ in secondary_groups) + " | ---: |",
            ]
        )
        for primary_group in primary_groups:
            returns = [
                _number(cells[(primary_group, secondary_group)])
                for secondary_group in secondary_groups
            ]
            lines.append(
                f"| T{primary_group} | "
                + " | ".join(returns)
                + f" | {_number(spreads[primary_group])} |"
            )

    metrics = report.model_metrics
    lines.extend(
        [
            "",
            "### Model Metrics",
            "",
            "| R-squared | Adjusted R-squared | RMSE | Information Coefficient | Observations |",
            "| ---: | ---: | ---: | ---: | ---: |",
            (
                f"| {_number(metrics.r_squared)} | "
                f"{_number(metrics.adjusted_r_squared)} | "
                f"{_number(metrics.rmse)} | "
                f"{_number(metrics.information_coefficient)} | "
                f"{metrics.observations} |"
            ),
            "",
            "## Robustness",
            "",
            report.robustness_summary,
            "",
            "| Check | Method | Result | Passed |",
            "| --- | --- | --- | :---: |",
        ]
    )
    if report.robustness_checks:
        for check in report.robustness_checks:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _cell(check.name),
                        _cell(check.method),
                        _cell(check.result),
                        "Yes" if check.passed else "No",
                    ]
                )
                + " |"
            )
    else:
        lines.append("| None reported | N/A | N/A | No |")

    lines.extend(["", "## Risk Disclosures", ""])
    lines.extend(f"- {risk}" for risk in report.risk_disclosures)
    lines.extend(["", "## Limitations", ""])
    lines.extend(f"- {item}" for item in report.limitations)
    lines.extend(["", "## Recommendations", ""])
    lines.extend(f"- {item}" for item in report.recommendations)
    lines.extend(["", "## Committee Review", ""])
    if report.unresolved_issues:
        lines.extend(
            [
                "| Severity | Category | Issue | Recommendation | Blocking |",
                "| --- | --- | --- | --- | :---: |",
            ]
        )
        for issue in report.unresolved_issues:
            lines.append(
                "| "
                + " | ".join(
                    [
                        issue.severity.value,
                        _cell(issue.category),
                        _cell(issue.description),
                        _cell(issue.recommendation),
                        "Yes" if issue.blocking else "No",
                    ]
                )
                + " |"
            )
    else:
        lines.append("No unresolved committee issues were recorded.")

    lines.extend(
        [
            "",
            "## Conclusion",
            "",
            report.conclusion,
            "",
            "## Provenance",
            "",
            f"- Source digest: `{report.source_digest}`",
            f"- Data fingerprint: `{report.data_fingerprint}`",
            "- Numeric tables were rendered directly from ExperimentResult.",
            "- This research output is not investment advice.",
            "",
        ]
    )
    return "\n".join(lines)


def save_markdown_report(report: FinalReport, path: Path) -> Path:
    """Persist a deterministic Markdown report."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown_report(report), encoding="utf-8")
    return path
