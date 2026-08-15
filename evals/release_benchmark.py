"""Evaluate service-line routing and checked-in showcase report contracts."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from graph.intent_router import route_request
from schemas.enums import AnalysisMethod, TaskType
from schemas.platform import ResearchRequest

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_VERSION = "1.5"


@dataclass(frozen=True)
class RouteCase:
    case_id: str
    request: ResearchRequest
    expected_workflow: str
    required_methods: tuple[AnalysisMethod, ...]


@dataclass(frozen=True)
class ShowcaseCase:
    case_id: str
    path: str
    required_headings: tuple[str, ...]
    minimum_characters: int


ROUTE_CASES = (
    RouteCase(
        "company_research_dcf",
        ResearchRequest(
            task_type=TaskType.COMPANY_RESEARCH,
            question="Assess financial quality and intrinsic value",
            companies=["Example Consumer Co"],
            topics=["financial_quality", "dcf"],
            as_of_date=date(2026, 8, 11),
        ),
        "company_research",
        (
            AnalysisMethod.FINANCIAL_STATEMENT_ANALYSIS,
            AnalysisMethod.DCF_VALUATION,
            AnalysisMethod.PEER_BENCHMARKING,
        ),
    ),
    RouteCase(
        "industry_research",
        ResearchRequest(
            task_type=TaskType.INDUSTRY_RESEARCH,
            question="Assess industry structure and scenarios",
            industries=["Electric vehicles"],
            as_of_date=date(2026, 8, 11),
        ),
        "industry_research",
        (AnalysisMethod.INDUSTRY_ANALYSIS, AnalysisMethod.SCENARIO_ANALYSIS),
    ),
    RouteCase(
        "quant_research",
        ResearchRequest(
            task_type=TaskType.QUANT_RESEARCH,
            question="Test whether momentum predicts future returns",
            topics=["momentum"],
            as_of_date=date(2026, 8, 11),
        ),
        "quant_research",
        (AnalysisMethod.REGRESSION, AnalysisMethod.PORTFOLIO_BACKTEST),
    ),
    RouteCase(
        "market_strategy",
        ResearchRequest(
            task_type=TaskType.MARKET_STRATEGY,
            question="Assess the current market regime",
            as_of_date=date(2026, 8, 11),
        ),
        "market_strategy",
        (
            AnalysisMethod.MARKET_REGIME_ANALYSIS,
            AnalysisMethod.SCENARIO_ANALYSIS,
        ),
    ),
    RouteCase(
        "event_study",
        ResearchRequest(
            task_type=TaskType.EVENT_STUDY,
            question="Measure the market response to an earnings warning",
            as_of_date=date(2026, 8, 11),
        ),
        "event_study",
        (AnalysisMethod.EVENT_STUDY,),
    ),
    RouteCase(
        "corporate_advisory",
        ResearchRequest(
            task_type=TaskType.CORPORATE_ADVISORY,
            question="Prioritise management risks and actions",
            companies=["Example Industrial Co"],
            as_of_date=date(2026, 8, 11),
        ),
        "corporate_advisory",
        (AnalysisMethod.STRATEGIC_DIAGNOSIS, AnalysisMethod.SCENARIO_ANALYSIS),
    ),
)

SHOWCASE_CASES = (
    ShowcaseCase(
        "risk_advisory",
        "reports/showcase/byd_risk_advisory.md",
        ("## 执行摘要", "## 风险优先级二维矩阵", "## 未来90天行动路线"),
        4_500,
    ),
    ShowcaseCase(
        "financial_anomaly_risk_warning",
        "reports/showcase/financial_anomaly_risk_warning.md",
        (
            "## 财务异常风险信号",
            "## 管理行动路线",
            "## 内部质量复核",
            "## 人工签署",
            "| 加权数据覆盖率 |",
            "| 行业阈值 |",
        ),
        4_000,
    ),
    ShowcaseCase(
        "company_research",
        "reports/showcase/moutai_company_research.md",
        ("## 执行摘要", "## 财务质量", "## 估值框架与同业比较", "## 研究委员会"),
        2_500,
    ),
    ShowcaseCase(
        "industry_research",
        "reports/showcase/baijiu_industry_research.md",
        (
            "## 产业链与价值分配",
            "## 需求、供给与竞争格局",
            "## 情景矩阵",
            "## 局限性与适用边界",
        ),
        2_500,
    ),
    ShowcaseCase(
        "event_intelligence",
        "reports/showcase/event_intelligence_showcase.md",
        ("## 更新决策", "## 建议重跑的报告部分", "## 治理规则"),
        500,
    ),
    ShowcaseCase(
        "statistical_event_study",
        "reports/showcase/byd_event_study.md",
        (
            "## 事件与研究假设",
            "## 方法与估计设计",
            "## 稳健性与污染检查",
            "## 局限性与可信边界",
        ),
        1_500,
    ),
    ShowcaseCase(
        "market_strategy",
        "reports/showcase/a_share_market_strategy.md",
        (
            "## Partner View",
            "## 风格与行业配置矩阵",
            "## 三情景策略矩阵",
            "## 风险与可信边界",
        ),
        2_000,
    ),
    ShowcaseCase(
        "momentum_research",
        "reports/showcase/momentum_factor_research.md",
        ("## 研究问题", "## 实验设计", "## 结构化结果", "## 结论与边界"),
        600,
    ),
    ShowcaseCase(
        "dcf_sensitivity",
        "reports/showcase/dcf_sensitivity_showcase.md",
        ("## Base Case", "## 核心假设", "## 每股价值敏感性矩阵", "## 可信边界"),
        600,
    ),
)


def _evaluate_route(case: RouteCase) -> dict[str, Any]:
    selection = route_request(case.request)
    methods = set(selection.analysis_methods)
    missing = sorted(
        method.value for method in set(case.required_methods).difference(methods)
    )
    workflow_matches = selection.workflow_name == case.expected_workflow
    return {
        "case_id": case.case_id,
        "passed": workflow_matches and not missing,
        "workflow": selection.workflow_name,
        "missing_methods": missing,
    }


def _evaluate_showcase(case: ShowcaseCase, root: Path) -> dict[str, Any]:
    path = root / case.path
    if not path.is_file():
        return {
            "case_id": case.case_id,
            "passed": False,
            "missing_headings": list(case.required_headings),
            "length_ok": False,
        }
    text = path.read_text(encoding="utf-8")
    missing = [heading for heading in case.required_headings if heading not in text]
    length_ok = len(text) >= case.minimum_characters
    return {
        "case_id": case.case_id,
        "passed": not missing and length_ok,
        "missing_headings": missing,
        "length_ok": length_ok,
    }


def build_release_evaluation(root: Path = ROOT) -> dict[str, Any]:
    """Return a deterministic, credential-free release evaluation."""
    route_results = [_evaluate_route(case) for case in ROUTE_CASES]
    showcase_results = [_evaluate_showcase(case, root) for case in SHOWCASE_CASES]
    results = [*route_results, *showcase_results]
    passed = sum(result["passed"] for result in results)
    return {
        "benchmark_version": BENCHMARK_VERSION,
        "summary": {
            "total": len(results),
            "passed": passed,
            "failed": len(results) - passed,
            "pass_rate": passed / len(results),
        },
        "route_cases": route_results,
        "showcase_cases": showcase_results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--baseline",
        type=Path,
        default=ROOT / "evals" / "baseline.json",
    )
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    current = build_release_evaluation()
    if args.write:
        args.baseline.write_text(
            json.dumps(current, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Evaluation baseline written: {args.baseline}")
        return 0
    if not args.baseline.is_file():
        print(f"Evaluation baseline is missing: {args.baseline}")
        return 1
    expected = json.loads(args.baseline.read_text(encoding="utf-8"))
    if current != expected:
        print("Release evaluation differs from the approved baseline.")
        print(json.dumps(current, ensure_ascii=False, indent=2))
        return 1
    print(
        "Release evaluation passed: "
        f"{current['summary']['passed']}/{current['summary']['total']} cases."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
