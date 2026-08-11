"""Offline Moutai fixture proving cross-industry company-research reuse."""

from datetime import date, datetime
from pathlib import Path

from analysis_engines.router import AnalysisEngineRegistry
from graph.company_research import build_company_research_workflow
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
            evidence_id="MT-E1",
            source_type="annual_report",
            title="贵州茅台2025年年度报告",
            source_name="贵州茅台股份有限公司官网",
            url=(
                "https://www.moutaichina.com/mtgf/articleFileDir/2026-04/17/"
                "07cf01cc11a14ea18cfadf9ebe2a4eb3.pdf"
            ),
            published_at=datetime(2026, 4, 17),
            retrieved_at=retrieved,
            summary=("披露2025年收入、利润、经营现金流、ROE及产品和渠道经营信息。"),
        ),
        EvidenceRecord(
            evidence_id="MT-E2",
            source_type="company_profile",
            title="贵州茅台公司简介",
            source_name="贵州茅台股份有限公司官网",
            url="https://www.moutaichina.com/mtgf/qygk/gsjj/index.html",
            retrieved_at=retrieved,
            summary="披露公司核心产品、品牌与产区定位。",
        ),
        EvidenceRecord(
            evidence_id="MT-E3",
            source_type="peer_annual_report",
            title="泸州老窖2024年年度报告",
            source_name="巨潮资讯网",
            url="https://static.cninfo.com.cn/finalpage/2025-04-28/1223350383.pdf",
            published_at=datetime(2025, 4, 28),
            retrieved_at=retrieved,
            summary="提供高端白酒同业的盈利、增长、渠道与回报指标比较口径。",
        ),
        EvidenceRecord(
            evidence_id="MT-E4",
            source_type="market_data_locator",
            title="贵州茅台证券信息",
            source_name="上海证券交易所",
            url=(
                "https://www.sse.com.cn/assortment/stock/list/info/company/"
                "index.shtml?COMPANY_CODE=600519"
            ),
            retrieved_at=retrieved,
            summary="提供证券基本信息；估值倍数仍需按实际研究截止日刷新。",
        ),
    ]


def _finding(identifier: str, statement: str, implication: str, evidence: str):
    return ResearchFinding(
        finding_id=identifier,
        statement=statement,
        implication=implication,
        evidence_ids=[evidence],
        status=EvidenceStatus.VERIFIED,
        confidence=0.9,
    )


def _engine(method: AnalysisMethod):
    fixtures = {
        AnalysisMethod.FINANCIAL_STATEMENT_ANALYSIS: AnalysisArtifact(
            method=method,
            title="财务质量",
            summary=(
                "2025年营业收入1,688.38亿元，同比下降1.21%；归母净利润"
                "823.20亿元，同比下降4.53%；经营现金流615.22亿元，同比下降"
                "33.46%。盈利能力仍高，但增长与现金转化较上年承压。"
            ),
            findings=[
                _finding(
                    "MT-F1",
                    "2025年收入、归母净利润和经营现金流均较2024年回落。",
                    "研究重点应从绝对盈利水平转向需求韧性、费用效率与现金转化。",
                    "MT-E1",
                )
            ],
            metrics={
                "2025营业收入": "1,688.38亿元 / -1.21%",
                "2025归母净利润": "823.20亿元 / -4.53%",
                "2025经营现金流": "615.22亿元 / -33.46%",
                "加权平均ROE": "32.53% / 同比-3.49pct",
            },
            limitations=["现金流变化仍需结合合同负债、税费和营运资本附注拆解。"],
        ),
        AnalysisMethod.STRATEGIC_DIAGNOSIS: AnalysisArtifact(
            method=method,
            title="商业模式与竞争位置",
            summary=(
                "核心品牌、稀缺产区和高端价格带构成主要竞争壁垒；研究焦点是"
                "行业需求调整期内的品牌势能能否转化为稳定动销和渠道秩序。"
            ),
            findings=[
                _finding(
                    "MT-F2",
                    "公司核心产品具有明确的品牌、产区与高端消费定位。",
                    "长期竞争优势较强，但短期收入兑现仍受终端需求与渠道行为影响。",
                    "MT-E2",
                )
            ],
            metrics={"竞争优势": "品牌 / 产区 / 产品稀缺性"},
            limitations=["未接入批价、渠道库存和终端动销的高频数据库。"],
        ),
        AnalysisMethod.RELATIVE_VALUATION: AnalysisArtifact(
            method=method,
            title="相对估值框架",
            summary=(
                "估值应围绕盈利增速、自由现金流、ROE和分红能力建立情景区间；"
                "本离线案例不固化易过期的市场价格，也不输出目标价。"
            ),
            findings=[
                _finding(
                    "MT-F3",
                    "证券信息可公开定位，但估值倍数必须按研究截止日重新计算。",
                    "在增长放缓阶段，应检验估值溢价是否获得现金流和股东回报支持。",
                    "MT-E4",
                )
            ],
            metrics={"估值状态": "需按截止日刷新PE / 自由现金流收益率"},
            assumptions=["市场价格、盈利预测和同业口径使用同一截止日。"],
            limitations=["案例未固化实时价格，因此不形成估值结论或目标价。"],
        ),
        AnalysisMethod.PEER_BENCHMARKING: AnalysisArtifact(
            method=method,
            title="同业比较",
            summary=(
                "同业比较应覆盖收入与利润增速、合同负债、现金转化、ROE、渠道"
                "结构和股东回报，并显式处理报告期不一致。"
            ),
            findings=[
                _finding(
                    "MT-F4",
                    "公开同业年报支持对白酒企业盈利质量和渠道策略进行对照。",
                    "只有在统一报告期和会计口径后，领先指标才能支持估值溢价判断。",
                    "MT-E3",
                )
            ],
            metrics={"同业基准": "高端白酒 / 统一报告期后比较"},
            limitations=["当前同业证据为2024年，落后于公司2025年报告期。"],
        ),
    }

    def execute(_context):
        return fixtures[method]

    return execute


def run_moutai_company_research_demo(report_path: str | Path | None = None):
    registry = AnalysisEngineRegistry()
    for method in (
        AnalysisMethod.FINANCIAL_STATEMENT_ANALYSIS,
        AnalysisMethod.STRATEGIC_DIAGNOSIS,
        AnalysisMethod.RELATIVE_VALUATION,
        AnalysisMethod.PEER_BENCHMARKING,
    ):
        registry.register(method, _engine(method))
    target = (
        Path(report_path)
        if report_path
        else (
            Path(__file__).resolve().parents[1]
            / "reports"
            / "company_research"
            / "moutai_company_research_demo.md"
        )
    )
    workflow = build_company_research_workflow(registry, report_path=target)
    request = ResearchRequest(
        task_type=TaskType.COMPANY_RESEARCH,
        question="研究贵州茅台的财务质量、竞争优势、同业位置与估值框架。",
        objective="形成可追溯、可更新的上市公司研究报告。",
        companies=["贵州茅台酒股份有限公司"],
        securities=["600519.SH"],
        topics=["financial_quality", "competitive_position", "valuation"],
        as_of_date=AS_OF_DATE,
        public_data_only=True,
        debate_requested=False,
    )
    return workflow.invoke(
        {
            "request": request,
            "analysis_context": {"evidence": _evidence()},
            "revision_count": 0,
            "max_revisions": 2,
        }
    )


if __name__ == "__main__":
    result = run_moutai_company_research_demo()
    print("Company: 贵州茅台酒股份有限公司")
    print("Review:", result["company_research_review"].decision.value)
    print("Report:", result["report_markdown_path"])
