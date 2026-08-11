from pathlib import Path

from examples.moutai_company_research_demo import run_moutai_company_research_demo
from schemas.enums import ReviewDecision


def test_moutai_demo_proves_cross_industry_company_research(tmp_path: Path) -> None:
    output = tmp_path / "moutai.md"
    result = run_moutai_company_research_demo(output)

    assert result["company_research_review"].decision == ReviewDecision.APPROVED
    report = result["company_research_report"]
    assert report.company_name == "贵州茅台酒股份有限公司"
    assert report.key_metrics["2025营业收入"] == "1,688.38亿元 / -1.21%"
    content = output.read_text(encoding="utf-8")
    assert "### 关键指标快照" in content
    assert "## 商业模式与竞争位置" in content
    assert "MT-E1" in content
