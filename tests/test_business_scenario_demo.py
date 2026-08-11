from pathlib import Path

from examples.business_risk_consulting_demo import (
    run_business_risk_consulting_demo,
)


def test_business_risk_consulting_demo_produces_decision_summary(
    tmp_path: Path,
) -> None:
    report = tmp_path / "risk-consulting.md"

    result = run_business_risk_consulting_demo(report)

    assert result["company"] == "比亚迪股份有限公司"
    assert "盈利质量与现金转化" in result["high_priority_risks"]
    assert result["management_focus"]
    assert result["committee_synthesis"]
    assert result["report_path"] == str(report)
    assert report.is_file()
    content = report.read_text(encoding="utf-8")
    assert "Partner View｜核心判断" in content
    assert "风险优先级二维矩阵" in content
    assert "未来90天行动路线" in content
    assert "Owner" in content
    assert "KPI / 触发指标" in content
