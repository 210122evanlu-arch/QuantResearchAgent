import json
import sys
from pathlib import Path

from evals.release_benchmark import ROOT, build_release_evaluation, main


def test_approved_release_benchmark_passes() -> None:
    result = build_release_evaluation(ROOT)

    assert result["summary"] == {
        "total": 15,
        "passed": 15,
        "failed": 0,
        "pass_rate": 1.0,
    }
    assert {case["workflow"] for case in result["route_cases"]} == {
        "company_research",
        "industry_research",
        "quant_research",
        "market_strategy",
        "event_study",
        "corporate_advisory",
    }


def test_missing_showcases_fail_without_hiding_route_results(tmp_path: Path) -> None:
    result = build_release_evaluation(tmp_path)

    assert result["summary"]["passed"] == 6
    assert result["summary"]["failed"] == 9
    assert all(case["passed"] for case in result["route_cases"])
    assert not any(case["passed"] for case in result["showcase_cases"])


def test_baseline_cli_write_check_and_detect_change(
    monkeypatch, tmp_path: Path
) -> None:
    baseline = tmp_path / "baseline.json"
    monkeypatch.setattr(
        sys,
        "argv",
        ["release_benchmark", "--baseline", str(baseline), "--write"],
    )
    assert main() == 0

    monkeypatch.setattr(
        sys,
        "argv",
        ["release_benchmark", "--baseline", str(baseline)],
    )
    assert main() == 0

    changed = json.loads(baseline.read_text(encoding="utf-8"))
    changed["benchmark_version"] = "stale"
    baseline.write_text(json.dumps(changed), encoding="utf-8")
    assert main() == 1


def test_baseline_cli_rejects_missing_file(monkeypatch, tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"
    monkeypatch.setattr(
        sys,
        "argv",
        ["release_benchmark", "--baseline", str(missing)],
    )

    assert main() == 1
