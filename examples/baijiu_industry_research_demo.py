"""Offline high-end baijiu industry fixture with public-source evidence."""

from datetime import date, datetime
from pathlib import Path

from analysis_engines.router import AnalysisEngineRegistry
from graph.industry_research import build_industry_research_workflow
from schemas.enums import AnalysisMethod, EvidenceStatus, TaskType
from schemas.platform import (
    AnalysisArtifact,
    EvidenceRecord,
    ResearchFinding,
    ResearchRequest,
)

AS_OF_DATE = date(2026, 8, 8)


def _evidence() -> list[EvidenceRecord]:
    retrieved = datetime(2026, 8, 8)
    return [
        EvidenceRecord(
            evidence_id="BJ-E1",
            source_type="annual_report",
            title="贵州茅台2025年年度报告",
            source_name="贵州茅台股份有限公司",
            url=(
                "https://www.moutaichina.com/mtgf/articleFileDir/2026-04/17/"
                "07cf01cc11a14ea18cfadf9ebe2a4eb3.pdf"
            ),
            published_at=datetime(2026, 4, 17),
            retrieved_at=retrieved,
            summary=(
                "披露2025年收入、利润、经营现金流、ROE及产品和渠道经营信息，"
                "用于观察高端白酒龙头的经营变化。"
            ),
        ),
        EvidenceRecord(
            evidence_id="BJ-E2",
            source_type="company_profile",
            title="贵州茅台公司简介",
            source_name="贵州茅台股份有限公司",
            url="https://www.moutaichina.com/mtgf/qygk/gsjj/index.html",
            retrieved_at=retrieved,
            summary="披露核心产品、品牌定位与产区属性，用于梳理行业竞争壁垒。",
        ),
        EvidenceRecord(
            evidence_id="BJ-E3",
            source_type="peer_annual_report",
            title="泸州老窖2024年年度报告",
            source_name="巨潮资讯网",
            url="https://static.cninfo.com.cn/finalpage/2025-04-28/1223350383.pdf",
            published_at=datetime(2025, 4, 28),
            retrieved_at=retrieved,
            summary=(
                "提供另一家高端白酒上市公司的盈利、增长、渠道与股东回报信息，"
                "形成有限同业对照。"
            ),
        ),
        EvidenceRecord(
            evidence_id="BJ-E4",
            source_type="market_data_locator",
            title="贵州茅台证券信息",
            source_name="上海证券交易所",
            url=(
                "https://www.sse.com.cn/assortment/stock/list/info/company/"
                "index.shtml?COMPANY_CODE=600519"
            ),
            retrieved_at=retrieved,
            summary=(
                "提供上市证券基本信息定位；市场价格和估值倍数仍需在实际研究截止日刷新。"
            ),
        ),
    ]


def _finding(
    identifier: str,
    statement: str,
    implication: str,
    evidence_ids: list[str],
    confidence: float = 0.88,
) -> ResearchFinding:
    return ResearchFinding(
        finding_id=identifier,
        statement=statement,
        implication=implication,
        evidence_ids=evidence_ids,
        status=EvidenceStatus.VERIFIED,
        confidence=confidence,
    )


def _engine(method: AnalysisMethod):
    fixtures = {
        AnalysisMethod.INDUSTRY_ANALYSIS: AnalysisArtifact(
            method=method,
            title="高端白酒行业结构与需求观察",
            summary=(
                "高端白酒的长期壁垒来自品牌心智、核心产区、优质基酒储备和渠道治理。"
                "贵州茅台2025年营业收入1,688.38亿元，同比下降1.21%；归母净利润"
                "823.20亿元，同比下降4.53%；经营现金流615.22亿元，同比下降33.46%。"
                "龙头仍具高盈利能力，但样本显示行业判断已不能只依赖品牌稀缺性，"
                "还需同步观察终端需求、渠道库存和现金转化。"
            ),
            findings=[
                _finding(
                    "BJ-F1",
                    "品牌、产区和优质基酒储备共同构成高端白酒的供给壁垒。",
                    "供给稀缺性支持长期价值，但并不能隔离短期需求和渠道周期。",
                    ["BJ-E1", "BJ-E2"],
                ),
                _finding(
                    "BJ-F1B",
                    "贵州茅台2025年收入、利润和经营现金流均较上年回落。",
                    "行业监测重心应由单一盈利水平扩展至动销、库存和现金转化。",
                    ["BJ-E1"],
                ),
            ],
            metrics={
                "贵州茅台2025营业收入": "1,688.38亿元 / -1.21%",
                "贵州茅台2025归母净利润": "823.20亿元 / -4.53%",
                "贵州茅台2025经营现金流": "615.22亿元 / -33.46%",
                "贵州茅台加权平均ROE": "32.53% / 同比-3.49pct",
            },
            limitations=[
                "公开材料未覆盖完整渠道库存、批价和终端动销高频序列。",
            ],
        ),
        AnalysisMethod.PEER_BENCHMARKING: AnalysisArtifact(
            method=method,
            title="龙头公司有限同业对照",
            summary=(
                "本案例以贵州茅台2025年报和泸州老窖2024年报建立两家公司快照。"
                "可比较维度包括收入与利润增长、现金转化、ROE、产品结构、渠道结构"
                "和股东回报；由于报告期不一致，结果用于提出问题与监测框架，"
                "不用于形成严格行业排名。"
            ),
            findings=[
                _finding(
                    "BJ-F2",
                    "两家龙头公司的公开年报可以支持盈利质量和渠道策略的结构化对照。",
                    "正式横向排名前必须统一报告期、会计口径和产品分类。",
                    ["BJ-E1", "BJ-E3"],
                ),
                _finding(
                    "BJ-F2B",
                    "证券信息可公开定位，但实时估值必须按研究截止日重新计算。",
                    "行业观点与证券估值应分层表达，避免用过期倍数支持投资结论。",
                    ["BJ-E4"],
                ),
            ],
            metrics={
                "对照样本": "贵州茅台、泸州老窖",
                "口径状态": "报告期不同，尚未形成严格排名",
            },
            limitations=[
                "仅覆盖两家公司，不能代表高端白酒全部上市公司和区域品牌。",
                "泸州老窖证据期为2024年，落后于贵州茅台2025年报告期。",
            ],
        ),
        AnalysisMethod.SCENARIO_ANALYSIS: AnalysisArtifact(
            method=method,
            title="需求与渠道情景分析",
            summary=(
                "行业结论采用基准、下行情景和上行情景管理，不给出单点预测。"
                "触发变量聚焦终端需求、渠道库存、核心产品价格、现金转化和费用效率，"
                "以便在新证据出现时重估观点。"
            ),
            findings=[
                _finding(
                    "BJ-F3",
                    "当前公开样本更适合支持有条件的行业判断，而非确定性增长预测。",
                    "可将龙头品牌韧性视为机会，同时为需求与渠道压力设置下行情景。",
                    ["BJ-E1", "BJ-E3"],
                )
            ],
            metrics={"情景数量": "3", "刷新机制": "触发指标变化后重新评估"},
            assumptions=["未披露的高频渠道数据不会被模型自行推断为已验证事实。"],
            limitations=["情景触发阈值需接入连续渠道与市场数据后量化。"],
        ),
    }

    def execute(_context):
        return fixtures[method]

    return execute


def run_baijiu_industry_research_demo(report_path: str | Path | None = None):
    registry = AnalysisEngineRegistry()
    for method in (
        AnalysisMethod.INDUSTRY_ANALYSIS,
        AnalysisMethod.PEER_BENCHMARKING,
        AnalysisMethod.SCENARIO_ANALYSIS,
    ):
        registry.register(method, _engine(method))
    target = (
        Path(report_path)
        if report_path
        else (
            Path(__file__).resolve().parents[1]
            / "reports"
            / "industry_research"
            / "baijiu_industry_research_demo.md"
        )
    )
    workflow = build_industry_research_workflow(registry, report_path=target)
    request = ResearchRequest(
        task_type=TaskType.INDUSTRY_RESEARCH,
        question="高端白酒上市公司当前呈现怎样的经营分化，未来有哪些关键情景？",
        objective="形成证据可追溯、可持续更新的行业研究与监测框架。",
        industries=["中国高端白酒上市公司"],
        topics=["industry_structure", "peer_comparison", "scenario_analysis"],
        as_of_date=AS_OF_DATE,
        public_data_only=True,
        debate_requested=False,
    )
    return workflow.invoke(
        {
            "request": request,
            "analysis_context": {
                "evidence": _evidence(),
                "value_chain": [
                    "粮食与包装供应",
                    "基酒酿造与储存",
                    "品牌运营",
                    "经销与直营渠道",
                    "商务及个人消费",
                ],
                "scenarios": [
                    {
                        "name": "基准情景：弱复苏与结构分化",
                        "trigger": "高端需求和渠道库存逐步企稳，但增长未回到高景气水平",
                        "implications": [
                            "品牌与现金流质量继续决定公司分化",
                            "行业估值更多依赖盈利兑现而非单纯提价预期",
                        ],
                        "monitoring_indicators": [
                            "核心产品批价与终端成交价",
                            "合同负债及经营现金流",
                        ],
                    },
                    {
                        "name": "下行情景：需求与渠道压力延续",
                        "trigger": "批价持续走弱、库存去化慢于预期且现金转化继续下降",
                        "implications": [
                            "企业可能加大费用或调整发货节奏",
                            "弱品牌和单一渠道暴露更高",
                        ],
                        "monitoring_indicators": [
                            "渠道库存周转天数",
                            "销售费用率与经销商数量变化",
                        ],
                    },
                    {
                        "name": "上行情景：需求修复与渠道再平衡",
                        "trigger": "终端动销连续改善、批价稳定且经营现金流恢复",
                        "implications": [
                            "龙头盈利弹性和品牌溢价重新获得验证",
                            "行业关注点由防守转向份额与产品升级",
                        ],
                        "monitoring_indicators": [
                            "季度收入与利润增速",
                            "直营占比、产品结构和回款质量",
                        ],
                    },
                ],
            },
            "revision_count": 0,
            "max_revisions": 2,
        }
    )


if __name__ == "__main__":
    result = run_baijiu_industry_research_demo()
    print("Industry: 中国高端白酒上市公司")
    print("Review:", result["industry_research_review"].decision.value)
    print("Report:", result["report_markdown_path"])
