"""Offline A-share market strategy demo using official evidence locators."""

from datetime import date, datetime
from pathlib import Path

from analysis_engines.router import AnalysisEngineRegistry
from graph.market_strategy import build_market_strategy_workflow
from schemas.enums import AnalysisMethod, EvidenceStatus, TaskType
from schemas.market_strategy import MarketSignalSnapshot
from schemas.platform import (
    AnalysisArtifact,
    EvidenceRecord,
    ResearchFinding,
    ResearchRequest,
)
from tools.market_strategy import assess_market_regime

AS_OF_DATE = date(2025, 2, 28)


def _evidence() -> list[EvidenceRecord]:
    retrieved = datetime(2026, 8, 11)
    return [
        EvidenceRecord(
            evidence_id="MS-E1",
            source_type="official_statistics",
            title="中华人民共和国2024年国民经济和社会发展统计公报",
            source_name="国家统计局",
            url="https://www.stats.gov.cn/sj/zxfb/202502/t20250228_1958817.html",
            published_at=datetime(2025, 2, 28),
            retrieved_at=retrieved,
            summary=(
                "披露2024年GDP同比增长5.0%，社会消费品零售总额同比增长3.5%，"
                "用于评估增长与内需环境。"
            ),
        ),
        EvidenceRecord(
            evidence_id="MS-E2",
            source_type="central_bank_report",
            title="2024年第四季度中国货币政策执行报告",
            source_name="中国人民银行",
            url=(
                "https://www.pbc.gov.cn/goutongjiaoliu/113456/113469/"
                "2025092212554550369/index.html"
            ),
            published_at=datetime(2025, 2, 13),
            retrieved_at=retrieved,
            summary=(
                "披露2024年两次降准合计1个百分点、政策利率下调0.3个百分点，"
                "年末社融存量和M2同比分别增长8.0%和7.3%。"
            ),
        ),
        EvidenceRecord(
            evidence_id="MS-E3",
            source_type="exchange_announcement",
            title="关于发布上证综合全收益指数实时行情的公告",
            source_name="上海证券交易所",
            url=(
                "https://www.sse.com.cn/market/sseindex/diclosure/c/"
                "c_20240715_10759849.shtml"
            ),
            published_at=datetime(2024, 7, 15),
            retrieved_at=retrieved,
            summary=(
                "上交所与中证指数有限公司自2024年7月29日起发布上证综合全收益"
                "指数实时行情，为观察包含分红的市场整体收益提供公开基准。"
            ),
        ),
    ]


def _snapshot() -> MarketSignalSnapshot:
    return MarketSignalSnapshot(
        growth_momentum=0.15,
        liquidity_support=0.65,
        valuation_attractiveness=0.20,
        earnings_momentum=0.05,
        risk_appetite=0.10,
        provenance=(
            "基于官方宏观与政策材料构造的确定性离线归一化夹具；"
            "估值、盈利和风险偏好信号不代表实时市场读数"
        ),
    )


def _finding(
    identifier: str,
    statement: str,
    implication: str,
    evidence_ids: list[str],
) -> ResearchFinding:
    return ResearchFinding(
        finding_id=identifier,
        statement=statement,
        implication=implication,
        evidence_ids=evidence_ids,
        status=EvidenceStatus.VERIFIED,
        confidence=0.9,
    )


def _engine(method: AnalysisMethod):
    assessment = assess_market_regime(_snapshot())
    fixtures = {
        AnalysisMethod.MARKET_REGIME_ANALYSIS: AnalysisArtifact(
            method=method,
            title="增长、流动性与市场环境",
            summary=(
                "2024年经济保持增长，内需修复速度相对温和；货币政策工具和融资成本"
                "下降为流动性环境提供支撑。确定性信号评分为"
                f"{assessment.score:.3f}，对应过渡环境，而不是单边风险偏好上行。"
            ),
            findings=[
                _finding(
                    "MS-F1",
                    "2024年GDP同比增长5.0%，社会消费品零售总额同比增长3.5%。",
                    "增长保持韧性，但消费修复仍需持续监测，配置不宜只依赖总量增长。",
                    ["MS-E1"],
                ),
                _finding(
                    "MS-F2",
                    "2024年降准、政策利率下调及结构工具共同强化流动性支持。",
                    "政策环境对估值形成支撑，但资金宽松仍需转化为盈利和风险偏好改善。",
                    ["MS-E2"],
                ),
                _finding(
                    "MS-F3",
                    "上证综合全收益指数提供包含现金分红的市场整体收益观察口径。",
                    "市场与策略评价应优先采用包含股息的总回报基准。",
                    ["MS-E3"],
                ),
            ],
            metrics={
                "2024 GDP增速": "5.0%",
                "2024社零增速": "3.5%",
                "年末社融存量增速": "8.0%",
                "年末M2增速": "7.3%",
                "确定性环境评分": f"{assessment.score:.3f}",
            },
            limitations=[
                "归一化市场信号为离线方法夹具，并非实时行情或盈利预测。",
            ],
        ),
        AnalysisMethod.SCENARIO_ANALYSIS: AnalysisArtifact(
            method=method,
            title="市场策略情景",
            summary=(
                "策略以基准、上行和下行情景管理，触发变量覆盖内需、盈利、流动性、"
                "估值和风险偏好；情景概率用于表达研究判断，不是客观发生频率。"
            ),
            findings=[
                _finding(
                    "MS-F4",
                    "增长与政策支持同时存在，但当前证据不支持确定性单边行情判断。",
                    "组合应采用核心—卫星结构，并为信号变化保留动态再平衡空间。",
                    ["MS-E1", "MS-E2"],
                )
            ],
            metrics={"情景数": "3", "配置原则": "条件触发 / 动态再平衡"},
            limitations=["情景概率和风格观点需要用实际市场数据持续刷新。"],
        ),
    }

    def execute(_context):
        return fixtures[method]

    return execute


def _context() -> dict:
    snapshot = _snapshot()
    return {
        "evidence": _evidence(),
        "regime_assessment": assess_market_regime(snapshot),
        "signal_provenance": snapshot.provenance,
        "horizon": "未来3—6个月",
        "style_views": [
            {
                "segment": "大盘质量",
                "stance": "overweight",
                "rationale": "过渡环境优先考虑现金流、盈利可见度和基准代表性。",
                "catalysts": ["盈利兑现", "分红与回购"],
                "risks": ["风险偏好快速扩张导致相对收益落后"],
            },
            {
                "segment": "小盘高弹性",
                "stance": "neutral",
                "rationale": "流动性有支撑，但盈利和风险偏好尚未形成一致信号。",
                "catalysts": ["成交活跃度提升", "盈利预期上修"],
                "risks": ["波动放大", "流动性反转"],
            },
            {
                "segment": "高股息",
                "stance": "overweight",
                "rationale": "总回报口径和现金回报在过渡环境中具有组合稳定作用。",
                "catalysts": ["分红稳定", "无风险利率下行"],
                "risks": ["利率反弹", "盈利下修"],
            },
        ],
        "sector_views": [
            {
                "segment": "科技与高端制造",
                "stance": "overweight",
                "rationale": "政策工具支持科技创新，但应以订单和盈利验证筛选。",
                "catalysts": ["资本开支改善", "订单兑现"],
                "risks": ["估值扩张快于盈利", "外部需求波动"],
            },
            {
                "segment": "消费",
                "stance": "neutral",
                "rationale": "社零保持增长，但需求修复的广度和持续性仍待验证。",
                "catalysts": ["收入预期改善", "消费政策传导"],
                "risks": ["需求修复低于预期"],
            },
            {
                "segment": "金融与公用事业",
                "stance": "neutral",
                "rationale": "可提供股息与防御属性，但需关注利差、资本开支和监管变化。",
                "catalysts": ["资产质量稳定", "现金回报提升"],
                "risks": ["净息差承压", "政策定价变化"],
            },
        ],
        "scenarios": [
            {
                "name": "基准：政策托底与结构分化",
                "probability": 0.55,
                "triggers": ["增长保持韧性", "流动性充裕但盈利改善温和"],
                "market_implications": ["指数震荡", "质量与主题机会并存"],
                "preferred_exposures": ["大盘质量", "高股息", "有盈利验证的科技制造"],
            },
            {
                "name": "上行：盈利与风险偏好共振",
                "probability": 0.25,
                "triggers": ["盈利预期连续上修", "成交与资金风险偏好同步改善"],
                "market_implications": ["估值扩张", "中小盘和成长风格占优"],
                "preferred_exposures": ["成长", "小盘弹性", "可选消费"],
            },
            {
                "name": "下行：需求走弱或风险溢价上升",
                "probability": 0.20,
                "triggers": ["需求指标转弱", "外部冲击推升风险溢价"],
                "market_implications": ["波动上升", "估值与盈利双重承压"],
                "preferred_exposures": ["现金流质量", "高股息", "低波动防御"],
            },
        ],
        "monitoring_indicators": [
            "PMI、社零与工业增加值的方向变化",
            "社融、M2、资金利率与信用利差",
            "盈利预测上调/下调比例",
            "全收益指数、成交额与市场宽度",
            "主要风格相对强弱和估值分位",
        ],
    }


def run_a_share_market_strategy_demo(report_path: str | Path | None = None):
    registry = AnalysisEngineRegistry()
    for method in (
        AnalysisMethod.MARKET_REGIME_ANALYSIS,
        AnalysisMethod.SCENARIO_ANALYSIS,
    ):
        registry.register(method, _engine(method))
    target = (
        Path(report_path)
        if report_path
        else (
            Path(__file__).resolve().parents[1]
            / "reports"
            / "market_strategy"
            / "a_share_market_strategy_demo.md"
        )
    )
    workflow = build_market_strategy_workflow(registry, report_path=target)
    request = ResearchRequest(
        task_type=TaskType.MARKET_STRATEGY,
        question="2024年末A股处于怎样的市场环境，未来3—6个月如何管理配置情景？",
        objective="形成基于证据、信号评分和触发条件的市场策略框架。",
        topics=["market_regime", "style_rotation", "sector_allocation"],
        as_of_date=AS_OF_DATE,
        public_data_only=True,
    )
    return workflow.invoke(
        {
            "request": request,
            "analysis_context": _context(),
            "revision_count": 0,
            "max_revisions": 2,
        }
    )


if __name__ == "__main__":
    result = run_a_share_market_strategy_demo()
    print("Market: 中国A股市场")
    print("Regime:", result["market_strategy_report"].regime.value)
    print("Review:", result["market_strategy_review"].decision.value)
    print("Report:", result["report_markdown_path"])
