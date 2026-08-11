from pathlib import Path

from examples.dcf_valuation_demo import run_dcf_valuation_demo


def test_dcf_demo_generates_five_by_five_sensitivity_matrix(tmp_path: Path) -> None:
    result, report = run_dcf_valuation_demo(tmp_path / "dcf.md")
    assert len(result.sensitivity) == 25
    assert result.value_per_share > 0
    content = report.read_text(encoding="utf-8")
    assert "每股价值敏感性矩阵" in content
    assert "不对应真实公司" in content
