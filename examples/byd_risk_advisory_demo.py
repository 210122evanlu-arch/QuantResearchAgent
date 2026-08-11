"""Public-evidence BYD risk consultation with Debate Gate and Fake LLM debate."""

from datetime import date, datetime
from pathlib import Path

from graph.debate import create_debate_workflow
from graph.debate_gate import DebateGateConfig, build_gated_debate_workflow
from llm.fake import FakeStructuredLLM
from schemas.advisory import CompanyRiskProfile, RiskAssessment
from schemas.debate import ChallengerCase, ModeratorAssessment, ProponentCase
from schemas.enums import (
    AnalysisMethod,
    EvidenceStatus,
    IssueSeverity,
    TaskType,
)
from schemas.platform import (
    AnalysisArtifact,
    AnalysisBundle,
    EvidenceRecord,
    ResearchFinding,
    ResearchRequest,
)
from tools.advisory_report import render_risk_advisory_report, save_risk_advisory_report

AS_OF_DATE = date(2026, 8, 7)


def _evidence() -> list[EvidenceRecord]:
    return [
        EvidenceRecord(
            evidence_id="BYD-E1",
            source_type="annual_report_summary",
            title="比亚迪股份有限公司2025年年度报告摘要",
            source_name="巨潮资讯网",
            url="https://static.cninfo.com.cn/finalpage/2026-03-28/1225045350.PDF",
            document_id="2026-004",
            published_at=datetime(2026, 3, 28),
            retrieved_at=datetime(2026, 8, 7),
            summary=(
                "2025年收入同比增长3.46%，归母净利润下降18.97%，经营现金流"
                "净额下降55.69%，加权平均ROE由26.05%降至15.31%；摘要称审计"
                "意见为标准意见。"
            ),
        ),
        EvidenceRecord(
            evidence_id="BYD-E2",
            source_type="sales_announcement",
            title="比亚迪股份有限公司2026年4月产销快报",
            source_name="巨潮资讯网",
            url="https://static.cninfo.com.cn/finalpage/2026-05-06/1225277520.pdf",
            document_id="2026-021",
            published_at=datetime(2026, 5, 5),
            retrieved_at=datetime(2026, 8, 7),
            summary=(
                "2026年1—4月新能源汽车累计销量1,021,586辆，同比下降26.02%；"
                "4月出口135,098辆。公告提示产销数据未经审核。"
            ),
        ),
        EvidenceRecord(
            evidence_id="BYD-E3",
            source_type="guarantee_announcement",
            title="关于公司及其控股子公司提供对外担保额度的公告",
            source_name="巨潮资讯网",
            url="https://static.cninfo.com.cn/finalpage/2026-03-28/1225045363.PDF",
            document_id="2026-007",
            published_at=datetime(2026, 3, 28),
            retrieved_at=datetime(2026, 8, 7),
            summary=(
                "拟授权控股子公司相关担保额度合计不超过1,500亿元，其中对资产"
                "负债率70%及以上控股子公司的额度不超过1,400亿元；参股公司"
                "担保总额度不超过355.15亿元。该数字是授权上限，不是实际余额。"
            ),
        ),
        EvidenceRecord(
            evidence_id="BYD-E4",
            source_type="related_party_announcement",
            title="比亚迪股份有限公司2026年度日常关联交易预计公告",
            source_name="巨潮资讯网",
            url="https://static.cninfo.com.cn/finalpage/2026-03-28/1225045364.PDF",
            document_id="2026-008",
            published_at=datetime(2026, 3, 28),
            retrieved_at=datetime(2026, 8, 7),
            summary=(
                "2026年度日常关联交易预计总额不超过1,143,163.31万元；两名"
                "关联董事回避表决，公司披露该预计额不高于最近一期经审计净资产"
                "的5%。"
            ),
        ),
        EvidenceRecord(
            evidence_id="BYD-E5",
            source_type="investor_relations_record",
            title="比亚迪股份有限公司投资者关系活动记录表",
            source_name="巨潮资讯网",
            url="https://static.cninfo.com.cn/finalpage/2026-04-02/1225077004.PDF",
            document_id="2026-03",
            published_at=datetime(2026, 4, 2),
            retrieved_at=datetime(2026, 8, 7),
            summary=(
                "公司称2025年研发投入约634亿元、同比增长17%，并计划2026年末"
                "在全国建设20,000座闪充站；这些是技术韧性因素，也带来执行与"
                "资本投入监测需求。"
            ),
        ),
        EvidenceRecord(
            evidence_id="BYD-E6",
            source_type="voluntary_announcement",
            title="比亚迪股份有限公司自愿公告",
            source_name="巨潮资讯网",
            url="https://static.cninfo.com.cn/finalpage/2026-06-10/1225361412.PDF",
            document_id="2026-024",
            published_at=datetime(2026, 6, 9),
            retrieved_at=datetime(2026, 8, 7),
            summary=(
                "公司披露被美国国防部列入中国军工企业名单，同时说明该名单并非"
                "制裁名单，除美国国防部采购限制外不影响正常业务或证券交易；"
                "公司可能申请复核或诉讼。"
            ),
        ),
    ]


def _risk_profile() -> CompanyRiskProfile:
    return CompanyRiskProfile(
        company_name="比亚迪股份有限公司",
        security_code="002594.SZ",
        as_of_date=AS_OF_DATE,
        assessments=[
            RiskAssessment(
                risk_id="BYD-R1",
                category="盈利质量与现金转化",
                severity=IssueSeverity.HIGH,
                observation=(
                    "2025年收入增长3.46%，但归母净利润下降18.97%、经营现金流"
                    "下降55.69%，ROE下降10.74个百分点。"
                ),
                implication="增长、盈利和现金回收出现背离，需要拆解价格、成本及营运资本。",
                evidence_ids=["BYD-E1"],
                monitoring_indicators=[
                    "单车利润",
                    "经营现金流/净利润",
                    "应付及存货周转",
                ],
                mitigation_actions=[
                    "建立季度现金转化桥接表",
                    "对价格与原材料成本做压力测试",
                ],
                confidence=0.95,
            ),
            RiskAssessment(
                risk_id="BYD-R2",
                category="销量与竞争压力",
                severity=IssueSeverity.HIGH,
                observation="2026年1—4月新能源汽车累计销量同比下降26.02%。",
                implication="若降幅持续，产能利用率、促销强度和利润率可能承压。",
                evidence_ids=["BYD-E2"],
                monitoring_indicators=[
                    "月度销量同比",
                    "国内/出口结构",
                    "终端折扣和库存天数",
                ],
                mitigation_actions=[
                    "按地区和品牌拆解销量",
                    "设置销量—毛利双变量情景分析",
                ],
                confidence=0.95,
            ),
            RiskAssessment(
                risk_id="BYD-R3",
                category="担保与集团信用暴露",
                severity=IssueSeverity.HIGH,
                observation="2026年度相关担保授权上限合计可达1,855.15亿元。",
                implication=(
                    "授权额度不等于实际负债，但高负债率子公司额度较大，需持续核对"
                    "实际担保余额、期限、反担保和集中度。"
                ),
                evidence_ids=["BYD-E3"],
                monitoring_indicators=[
                    "实际担保余额",
                    "被担保主体负债率",
                    "逾期和代偿记录",
                ],
                mitigation_actions=[
                    "建立授权额与实际余额双口径台账",
                    "按子公司进行信用压力测试",
                ],
                confidence=0.75,
            ),
            RiskAssessment(
                risk_id="BYD-R4",
                category="关联交易治理",
                severity=IssueSeverity.MEDIUM,
                observation="2026年度预计日常关联交易上限约114.32亿元。",
                implication="程序披露和回避表决已执行，仍需监测定价公允性和交易集中度。",
                evidence_ids=["BYD-E4"],
                monitoring_indicators=[
                    "实际发生额/预计额",
                    "主要关联方集中度",
                    "毛利率差异",
                ],
                mitigation_actions=[
                    "定期进行非关联交易价格对标",
                    "披露主要交易增长原因",
                ],
                confidence=0.85,
            ),
            RiskAssessment(
                risk_id="BYD-R5",
                category="地缘政治与海外合规",
                severity=IssueSeverity.HIGH,
                observation="公司披露被美国国防部列入中国军工企业名单。",
                implication=(
                    "当前披露称该名单并非制裁名单且直接影响有限，但仍存在名单升级、"
                    "供应链审查、合作方风险偏好变化等尾部风险。"
                ),
                evidence_ids=["BYD-E6"],
                monitoring_indicators=[
                    "复核或诉讼进展",
                    "其他司法辖区措施",
                    "海外客户与融资变化",
                ],
                mitigation_actions=[
                    "建立国家级合规情景树",
                    "准备客户和供应商连续性预案",
                ],
                confidence=0.8,
            ),
            RiskAssessment(
                risk_id="BYD-R6",
                category="研发与基础设施执行",
                severity=IssueSeverity.MEDIUM,
                observation="公司称2025年研发投入约634亿元，并计划年末建设2万座闪充站。",
                implication="投入有助技术领先，但需检验建设节奏、利用率和资本回报。",
                evidence_ids=["BYD-E5"],
                monitoring_indicators=[
                    "闪充站投运数",
                    "单站利用率",
                    "研发费用资本化与产出",
                ],
                mitigation_actions=[
                    "分阶段设置投资门槛",
                    "按区域披露站点利用率与回收期",
                ],
                confidence=0.75,
            ),
        ],
        resilience_factors=[
            "2025年末归属于上市公司股东的净资产同比增长32.94%。",
            "公司披露2025年研发投入约634亿元，同比增长17%。",
            "2026年4月出口新能源汽车135,098辆，为国内需求压力提供一定结构性缓冲。",
            "年度报告摘要显示2025年审计意见为标准意见。",
        ],
        scope_limitations=[
            "本演示只使用列明的公开披露，没有接入完整年报附注、实时行情和供应链数据库。",
            "担保数字是股东会授权上限，不代表实际担保余额或已经发生的损失。",
            "2026年产销快报未经审核，不能替代经审计财务数据。",
            "未进行估值判断、信用评级或证券买卖建议。",
        ],
    )


def _analysis_node(state) -> dict:
    profile = _risk_profile()
    evidence = _evidence()
    findings = [
        ResearchFinding(
            finding_id=item.risk_id,
            statement=item.observation,
            implication=item.implication,
            evidence_ids=item.evidence_ids,
            status=(
                EvidenceStatus.VERIFIED
                if item.risk_id in {"BYD-R1", "BYD-R2", "BYD-R4"}
                else EvidenceStatus.INFERRED
            ),
            confidence=item.confidence,
        )
        for item in profile.assessments
    ]
    artifact = AnalysisArtifact(
        method=AnalysisMethod.STRATEGIC_DIAGNOSIS,
        title="比亚迪公开信息风险诊断",
        summary="识别六项风险主题及相应的监测和缓释行动。",
        findings=findings,
        limitations=profile.scope_limitations,
    )
    return {
        "risk_profile": profile,
        "analysis_bundle": AnalysisBundle(
            artifacts=[artifact],
            evidence=evidence,
            warnings=[
                "Actual guarantee balances were not available in this demo scope.",
                "Several implications are inferences rather than disclosed outcomes.",
            ],
        ),
        "current_stage": "company_risk_analysis",
    }


def _debate_responses() -> dict:
    return {
        ProponentCase: [
            {
                "thesis": "风险上升但仍存在可验证的经营和技术缓释因素。",
                "arguments": [
                    {
                        "argument_id": "BYD-P1",
                        "position": "support",
                        "claim": "公司仍有较强净资产和研发投入基础。",
                        "reasoning": "净资产增长和高研发投入可支撑风险应对。",
                        "evidence_ids": ["BYD-E1", "BYD-E5"],
                        "challenges_argument_ids": [],
                        "confidence": 0.8,
                    },
                    {
                        "argument_id": "BYD-P2",
                        "position": "support",
                        "claim": "海外销量可以部分缓冲国内销售压力。",
                        "reasoning": "4月出口量显示海外渠道具有现实贡献。",
                        "evidence_ids": ["BYD-E2"],
                        "challenges_argument_ids": [],
                        "confidence": 0.7,
                    },
                ],
                "acknowledged_limitations": ["出口单月数据不能证明利润缓释。"],
            },
            {
                "thesis": "可通过分层监控而非直接推断危机来管理已识别风险。",
                "arguments": [
                    {
                        "argument_id": "BYD-P3",
                        "position": "support",
                        "claim": "担保授权额不应被误读为实际债务。",
                        "reasoning": "公告明确披露的是可用额度，需要另查实际余额。",
                        "evidence_ids": ["BYD-E3"],
                        "challenges_argument_ids": [],
                        "confidence": 0.9,
                    },
                    {
                        "argument_id": "BYD-P4",
                        "position": "support",
                        "claim": "美国相关名单当前并非制裁名单。",
                        "reasoning": "公司公告列明现阶段直接限制的边界。",
                        "evidence_ids": ["BYD-E6"],
                        "challenges_argument_ids": [],
                        "confidence": 0.85,
                    },
                ],
                "acknowledged_limitations": ["未来政策升级仍无法由现有公告排除。"],
            },
        ],
        ChallengerCase: [
            {
                "counter_thesis": "缓释因素不足以抵消盈利、销量和尾部风险。",
                "arguments": [
                    {
                        "argument_id": "BYD-C1",
                        "position": "challenge",
                        "claim": "研发投入不能自动转化为现金回报。",
                        "reasoning": "经营现金流与利润在2025年均明显下降。",
                        "evidence_ids": ["BYD-E1", "BYD-E5"],
                        "challenges_argument_ids": ["BYD-P1"],
                        "confidence": 0.9,
                    },
                    {
                        "argument_id": "BYD-C2",
                        "position": "challenge",
                        "claim": "出口增长无法从现有材料证明能抵消销量和利润压力。",
                        "reasoning": "披露只给出销量，未给出出口利润率。",
                        "evidence_ids": ["BYD-E2"],
                        "challenges_argument_ids": ["BYD-P2"],
                        "confidence": 0.9,
                    },
                ],
                "requested_checks": ["补充国内与出口毛利率", "补充现金流桥接"],
            },
            {
                "counter_thesis": "口径澄清降低了误判，但数据缺口仍阻止低风险结论。",
                "arguments": [
                    {
                        "argument_id": "BYD-C3",
                        "position": "challenge",
                        "claim": "没有实际担保余额就无法量化信用暴露。",
                        "reasoning": "授权上限与存量风险是不同口径。",
                        "evidence_ids": ["BYD-E3"],
                        "challenges_argument_ids": ["BYD-P3"],
                        "confidence": 0.95,
                    },
                    {
                        "argument_id": "BYD-C4",
                        "position": "challenge",
                        "claim": "当前非制裁状态不能排除后续升级和合作方行为变化。",
                        "reasoning": "公告本身保留了复核或诉讼的可能。",
                        "evidence_ids": ["BYD-E6"],
                        "challenges_argument_ids": ["BYD-P4"],
                        "confidence": 0.85,
                    },
                ],
                "requested_checks": ["获取实际担保余额", "持续监控美国名单后续"],
            },
        ],
        ModeratorAssessment: [
            {
                "decision": "continue",
                "new_information_added": True,
                "resolved_issues": ["研发和出口是缓释因素而非风险消除证据。"],
                "unresolved_issues": ["担保口径和地缘风险边界需要澄清。"],
                "consensus_findings": ["盈利现金流和销量需要高优先级监控。"],
                "disputed_findings": ["当前缓释因素能否抵消主要压力。"],
                "rationale": "第二轮应区分授权上限与实际暴露，并界定名单影响。",
                "synthesis": "继续一轮，聚焦担保和地缘风险的口径。",
            },
            {
                "decision": "conclude",
                "new_information_added": True,
                "resolved_issues": [
                    "1,855.15亿元是担保授权上限而非实际余额。",
                    "公司披露美国相关名单当前并非制裁名单。",
                ],
                "unresolved_issues": [
                    "实际担保余额及压力损失未知。",
                    "出口业务盈利能力和地缘政策后续影响未知。",
                ],
                "consensus_findings": [
                    "盈利现金转化、销量和集团信用暴露应列为高优先级监控。",
                    "研发、出口和净资产是缓释因素，但不能直接抵消风险。",
                ],
                "disputed_findings": ["地缘风险是否会演变为实质业务限制。"],
                "rationale": "现有证据边界已经澄清，继续辩论不能替代缺失数据。",
                "synthesis": (
                    "建议维持高关注但避免把授权额度等同实际负债、把名单等同"
                    "制裁；下一步应获取担保余额、出口利润率和季度现金流桥接。"
                ),
            },
        ],
    }


def run_byd_risk_advisory_demo(report_path: str | Path | None = None):
    llm = FakeStructuredLLM(_debate_responses())
    debate = create_debate_workflow(llm)
    workflow = build_gated_debate_workflow(
        _analysis_node,
        debate,
        gate_config=DebateGateConfig(max_rounds=2),
    )
    request = ResearchRequest(
        task_type=TaskType.CORPORATE_ADVISORY,
        question="基于公开信息评估比亚迪的主要经营、财务和外部风险。",
        companies=["比亚迪股份有限公司"],
        securities=["002594.SZ"],
        topics=["financial_risk", "operational_risk", "governance", "geopolitics"],
        as_of_date=AS_OF_DATE,
        debate_requested=True,
    )
    result = workflow.invoke({"request": request})
    content = render_risk_advisory_report(
        result["risk_profile"],
        result["analysis_bundle"],
        result["debate_gate_result"],
        result.get("debate_result"),
    )
    target = report_path or (
        Path(__file__).resolve().parents[1]
        / "reports"
        / "advisory"
        / "byd_risk_advisory_demo.md"
    )
    result["report_markdown_path"] = str(save_risk_advisory_report(content, target))
    return result, llm


if __name__ == "__main__":
    final_state, fake_llm = run_byd_risk_advisory_demo()
    print("BYD public-data risk advisory: passed")
    print("Gate:", final_state["debate_gate_result"].decision.value)
    print(
        "Triggers:", [item.value for item in final_state["debate_gate_result"].triggers]
    )
    print("Debate rounds:", len(final_state["debate_result"].rounds))
    print("Report:", final_state["report_markdown_path"])
