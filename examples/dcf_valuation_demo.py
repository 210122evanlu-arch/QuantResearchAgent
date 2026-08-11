"""Assumption-explicit DCF and sensitivity-matrix showcase."""

from pathlib import Path

from schemas.valuation import DCFInput, DCFResult, DCFSensitivityConfig
from tools.valuation import run_dcf


def _inputs() -> DCFInput:
    return DCFInput.model_validate(
        {
            "currency": "CNY",
            "projections": [
                {"year": 1, "free_cash_flow": 1200},
                {"year": 2, "free_cash_flow": 1320},
                {"year": 3, "free_cash_flow": 1450},
                {"year": 4, "free_cash_flow": 1570},
                {"year": 5, "free_cash_flow": 1680},
            ],
            "discount_rate": 0.10,
            "terminal_growth_rate": 0.03,
            "net_debt": 2500,
            "shares_outstanding": 1000,
        }
    )


def _render(inputs: DCFInput, result: DCFResult) -> str:
    rates = sorted({item.discount_rate for item in result.sensitivity})
    growth = sorted({item.terminal_growth_rate for item in result.sensitivity})
    lookup = {
        (item.discount_rate, item.terminal_growth_rate): item.value_per_share
        for item in result.sensitivity
    }
    lines = [
        '<div align="center">',
        "",
        "<h1>现金流估值与敏感性分析</h1>",
        "",
        "<p><strong>Illustrative DCF Valuation</strong><br>",
        "显式预测 · 永续增长 · WACC × Terminal Growth</p>",
        "",
        "</div>",
        "",
        "## Base Case",
        "",
        "| 指标 | 结果 |",
        "| --- | ---: |",
        f"| 企业价值 | {result.enterprise_value:,.2f} {result.currency} |",
        f"| 股权价值 | {result.equity_value:,.2f} {result.currency} |",
        f"| 每股价值 | {result.value_per_share:,.2f} {result.currency} |",
        f"| 终值占企业价值 | {result.terminal_value_share:.1%} |",
        "",
        "## 核心假设",
        "",
        f"- WACC：{inputs.discount_rate:.1%}",
        f"- 永续增长率：{inputs.terminal_growth_rate:.1%}",
        f"- 净债务：{inputs.net_debt:,.2f} {inputs.currency}",
        f"- 稀释后股数：{inputs.shares_outstanding:,.2f}",
        "",
        "## 每股价值敏感性矩阵",
        "",
        "| WACC \\ g | " + " | ".join(f"{value:.1%}" for value in growth) + " |",
        "| --- | " + " | ".join("---:" for _ in growth) + " |",
    ]
    for rate in rates:
        lines.append(
            f"| **{rate:.1%}** | "
            + " | ".join(f"{lookup[(rate, value)]:.2f}" for value in growth)
            + " |"
        )
    lines.extend(
        [
            "",
            "## 可信边界",
            "",
            "该案例使用假设性现金流，只验证 DCF 和敏感性计算能力，不对应真实公司、"
            "目标价或投资建议。正式研究必须将预测假设关联至财务模型和证据 ID。",
            "",
            *(f"- Warning: {warning}" for warning in result.warnings),
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def run_dcf_valuation_demo(report_path: str | Path | None = None):
    inputs = _inputs()
    result = run_dcf(inputs, DCFSensitivityConfig(steps_each_side=2))
    target = (
        Path(report_path)
        if report_path
        else (
            Path(__file__).resolve().parents[1]
            / "reports"
            / "valuation"
            / "dcf_valuation_demo.md"
        )
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(_render(inputs, result), encoding="utf-8")
    return result, target.resolve()


if __name__ == "__main__":
    valuation, output = run_dcf_valuation_demo()
    print("Value per share:", valuation.value_per_share, valuation.currency)
    print("Sensitivity cells:", len(valuation.sensitivity))
    print("Report:", output)
