from math import nextafter
from pathlib import Path

import pytest
from pydantic import ValidationError

from agents.report import ReportConsistencyError, create_report_node
from examples.ivol_research_demo import run_ivol_fake_demo
from schemas.enums import ReviewDecision
from schemas.experiment import PortfolioCellResult
from schemas.report import FinalReport
from schemas.review import ReviewResult
from tools.report_generator import render_markdown_report


def test_end_to_end_markdown_uses_verified_state_values(tmp_path: Path) -> None:
    path = tmp_path / "ivol-report.md"

    state, _ = run_ivol_fake_demo(path)

    report = state["final_report"]
    experiment = state["experiment_result"]
    content = path.read_text(encoding="utf-8")
    assert report.statistical_findings == experiment.statistical_results
    assert report.model_metrics == experiment.model_metrics
    assert report.experiment_sample_size == experiment.sample_size
    assert report.experiment_data_fingerprint == experiment.data_fingerprint
    assert report.prepared_data_fingerprint == state["data_profile"].dataset_fingerprint
    assert f"{experiment.sample_size}" in content
    for result in experiment.statistical_results:
        assert f"{result.coefficient:.8g}" in content
        assert f"{result.p_value:.8g}" in content
    paper = state["research_analysis"].key_papers[0]
    assert paper.title in content
    assert paper.doi_or_url in content
    assert "Committee status: **APPROVED**" in content
    assert state["report_markdown_path"] == str(path.resolve())


def test_source_digest_is_stable_for_identical_verified_state(tmp_path: Path) -> None:
    first, _ = run_ivol_fake_demo(tmp_path / "first.md")
    second, _ = run_ivol_fake_demo(tmp_path / "second.md")

    assert first["final_report"].source_digest == second["final_report"].source_digest
    assert first["final_report"].artifact_path != second["final_report"].artifact_path


def test_source_digest_ignores_derived_paths_and_float_tail_noise() -> None:
    first, _ = run_ivol_fake_demo()
    second, _ = run_ivol_fake_demo()
    result = second["experiment_result"]
    coefficient = result.statistical_results[0].coefficient
    result.statistical_results[0].coefficient = nextafter(coefficient, float("inf"))
    result.artifact_path = "/a/different/output/location.json"
    second["data_profile"].data_sources = [
        "/home/runner/work/project/examples/data/ivol_fixture.csv"
    ]

    first_report = create_report_node()(first)["final_report"]
    second_report = create_report_node()(second)["final_report"]

    assert first_report.source_digest == second_report.source_digest


def test_unapproved_report_preserves_blocking_issue_and_prominent_status(
    tmp_path: Path,
) -> None:
    state, _ = run_ivol_fake_demo()
    state["review_result"] = ReviewResult.model_validate(
        {
            "issues": [
                {
                    "category": "robustness",
                    "problem_type": "experiment_issue",
                    "severity": "high",
                    "description": "Robustness remains unresolved.",
                    "recommendation": "Rerun the experiment.",
                    "evidence": ["experiment_result.robustness_checks"],
                }
            ],
            "decision": "need_revision",
            "revision_target": "experiment",
            "overall_assessment": "Revision limit reached.",
        }
    )
    state["revision_limit_reached"] = True
    path = tmp_path / "unapproved.md"

    result = create_report_node(path)(state)["final_report"]
    content = path.read_text(encoding="utf-8")

    assert result.review_decision == ReviewDecision.NEED_REVISION
    assert result.unresolved_issues[0].blocking is True
    assert any(
        "approval was not obtained" in item.casefold()
        for item in result.risk_disclosures
    )
    assert "NOT APPROVED — REVISION REQUIRED" in content
    assert "No formal research conclusion is approved" in result.conclusion


def test_final_report_schema_rejects_hidden_unapproved_status() -> None:
    state, _ = run_ivol_fake_demo()
    payload = state["final_report"].model_dump(mode="json")
    payload["review_decision"] = "need_revision"
    payload["risk_disclosures"] = ["Generic risk text only"]

    with pytest.raises(ValidationError, match="approval was not obtained"):
        FinalReport.model_validate(payload)


def test_report_copies_statistics_instead_of_sharing_mutable_objects() -> None:
    state, _ = run_ivol_fake_demo()
    report = create_report_node()(state)["final_report"]
    original = report.statistical_findings[0].coefficient

    state["experiment_result"].statistical_results[0].coefficient = 999.0

    assert report.statistical_findings[0].coefficient == original


def test_report_renders_sequential_portfolio_matrix() -> None:
    state, _ = run_ivol_fake_demo()
    state["experiment_result"].portfolio_results = [
        PortfolioCellResult(
            primary_group=turnover_group,
            secondary_group=ivol_group,
            mean_return=turnover_group / 100 + ivol_group / 1000,
            observations=10,
        )
        for turnover_group in range(1, 6)
        for ivol_group in range(1, 6)
    ]

    report = create_report_node()(state)["final_report"]
    content = render_markdown_report(report)

    assert "### Sequential Portfolio Returns" in content
    assert "| T1 | 0.011 | 0.012 | 0.013 | 0.014 | 0.015 | 0.004 |" in content
    assert "| T5 | 0.051 | 0.052 | 0.053 | 0.054 | 0.055 | 0.004 |" in content


def test_approved_report_rejects_data_fingerprint_mismatch() -> None:
    state, _ = run_ivol_fake_demo()
    state["experiment_result"].data_fingerprint = "sha256:different"

    with pytest.raises(ReportConsistencyError, match="fingerprints"):
        create_report_node()(state)


def test_checked_in_example_report_matches_deterministic_renderer(
    tmp_path: Path,
) -> None:
    generated = tmp_path / "generated.md"
    run_ivol_fake_demo(generated)
    project_root = Path(__file__).resolve().parents[1]
    checked_in = project_root / "reports" / "example_report.md"

    assert generated.read_text(encoding="utf-8") == checked_in.read_text(
        encoding="utf-8"
    )
