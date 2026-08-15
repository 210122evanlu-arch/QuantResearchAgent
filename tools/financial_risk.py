"""Deterministic and explainable financial-anomaly screening."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from schemas.enums import FinancialRiskCategory, FinancialRiskLevel, IssueSeverity
from schemas.financial_risk import (
    AuditTrail,
    FinancialRiskInput,
    FinancialRiskScorecard,
    FinancialRiskSignal,
    RiskAction,
)

METHODOLOGY_VERSION = "financial-risk-scorecard-1.0"


def _growth(current: float, prior: float) -> float | None:
    if prior == 0:
        return None
    return current / prior - 1


def _severity(triggered: bool, weight: float) -> IssueSeverity:
    if not triggered:
        return IssueSeverity.LOW
    if weight >= 15:
        return IssueSeverity.CRITICAL
    if weight >= 10:
        return IssueSeverity.HIGH
    return IssueSeverity.MEDIUM


def _action(
    owner: str, timeline: str, actions: list[str], kpis: list[str]
) -> RiskAction:
    return RiskAction(owner=owner, timeline=timeline, actions=actions, kpis=kpis)


def _signal(
    *,
    signal_id: str,
    category: FinancialRiskCategory,
    label: str,
    value: float | None,
    threshold: str,
    triggered: bool,
    observation: str,
    interpretation: str,
    evidence_ids: list[str],
    action: RiskAction,
    weight: float,
) -> FinancialRiskSignal:
    return FinancialRiskSignal(
        signal_id=signal_id,
        category=category,
        label=label,
        value=value,
        threshold=threshold,
        triggered=triggered,
        severity=_severity(triggered, weight),
        observation=observation,
        interpretation=interpretation,
        evidence_ids=evidence_ids,
        action=action,
        weight=weight,
    )


def screen_financial_anomalies(data: FinancialRiskInput) -> FinancialRiskScorecard:
    """Screen red flags without making fraud, audit, or legal conclusions."""
    current = data.current
    prior = data.prior
    evidence_ids = list(dict.fromkeys([*current.evidence_ids, *prior.evidence_ids]))
    revenue_growth = _growth(current.revenue, prior.revenue)
    receivable_growth = _growth(current.accounts_receivable, prior.accounts_receivable)
    inventory_growth = _growth(current.inventory, prior.inventory)
    cash_conversion = (
        current.operating_cash_flow / current.net_profit
        if current.net_profit > 0
        else None
    )
    accrual_ratio = (
        current.net_profit - current.operating_cash_flow
    ) / current.total_assets
    ar_gap = (
        receivable_growth - revenue_growth
        if receivable_growth is not None and revenue_growth is not None
        else None
    )
    inventory_gap = (
        inventory_growth - revenue_growth
        if inventory_growth is not None and revenue_growth is not None
        else None
    )
    margin_gap = (
        current.gross_margin - data.peer_gross_margin_median
        if data.peer_gross_margin_median is not None
        else None
    )
    non_recurring_ratio = (
        abs(current.non_recurring_profit) / abs(current.net_profit)
        if current.net_profit != 0
        else None
    )
    current_ratio = (
        current.current_assets / current.current_liabilities
        if current.current_liabilities > 0
        else None
    )
    net_debt = current.interest_bearing_debt - current.cash_and_equivalents
    net_debt_to_cfo = (
        net_debt / current.operating_cash_flow
        if current.operating_cash_flow > 0
        else None
    )

    signals = [
        _signal(
            signal_id="FR-CASH-CONVERSION",
            category=FinancialRiskCategory.EARNINGS_QUALITY,
            label="利润现金转化",
            value=cash_conversion,
            threshold="经营现金流/净利润 < 0.80，或盈利但经营现金流为负",
            triggered=(
                current.net_profit > 0
                and (cash_conversion is None or cash_conversion < 0.8)
            ),
            observation=f"经营现金流/净利润为 {cash_conversion:.2f}。"
            if cash_conversion is not None
            else "净利润与经营现金流无法形成有效正向转化比率。",
            interpretation="利润与现金回收背离，需要拆解营运资本和非现金项目。",
            evidence_ids=evidence_ids,
            action=_action(
                "CFO / 财务规划与分析",
                "30天",
                ["建立利润到经营现金流桥接表", "复核大额非现金损益"],
                ["经营现金流/净利润", "自由现金流"],
            ),
            weight=15,
        ),
        _signal(
            signal_id="FR-ACCRUAL",
            category=FinancialRiskCategory.EARNINGS_QUALITY,
            label="应计利润压力",
            value=accrual_ratio,
            threshold="(净利润-经营现金流)/总资产 > 0.10",
            triggered=accrual_ratio > 0.10,
            observation=f"应计利润比率为 {accrual_ratio:.2%}。",
            interpretation="较高应计项目可能降低盈利质量，需核对形成原因。",
            evidence_ids=evidence_ids,
            action=_action(
                "财务总监 / 内控负责人",
                "45天",
                ["按科目拆解应计项目", "抽查重大期末调整分录"],
                ["应计利润比率", "重大调整分录数量"],
            ),
            weight=10,
        ),
        _signal(
            signal_id="FR-AR-GAP",
            category=FinancialRiskCategory.WORKING_CAPITAL,
            label="应收增速偏离收入",
            value=ar_gap,
            threshold="应收账款增速－收入增速 > 15个百分点",
            triggered=ar_gap is not None and ar_gap > 0.15,
            observation=f"应收账款增速较收入增速高 {ar_gap:.2%}。"
            if ar_gap is not None
            else "基期为零，无法计算应收账款增速差。",
            interpretation="回款节奏可能弱于收入确认，需要核对账龄和客户集中度。",
            evidence_ids=evidence_ids,
            action=_action(
                "销售财务 / 信用管理负责人",
                "30天",
                ["开展客户与账龄穿透", "复核期后回款"],
                ["逾期应收占比", "期后回款率", "前五大客户集中度"],
            ),
            weight=12,
        ),
        _signal(
            signal_id="FR-INVENTORY-GAP",
            category=FinancialRiskCategory.WORKING_CAPITAL,
            label="存货增速偏离收入",
            value=inventory_gap,
            threshold="存货增速－收入增速 > 15个百分点",
            triggered=inventory_gap is not None and inventory_gap > 0.15,
            observation=f"存货增速较收入增速高 {inventory_gap:.2%}。"
            if inventory_gap is not None
            else "基期为零，无法计算存货增速差。",
            interpretation="库存积压或减值压力可能上升，需要结合库龄和订单验证。",
            evidence_ids=evidence_ids,
            action=_action(
                "供应链负责人 / 财务总监",
                "45天",
                ["按产品和库龄拆解存货", "对滞销品执行减值压力测试"],
                ["存货周转天数", "一年以上库龄占比", "减值覆盖率"],
            ),
            weight=10,
        ),
        _signal(
            signal_id="FR-MARGIN-PEER",
            category=FinancialRiskCategory.MARGIN,
            label="毛利率同业偏离",
            value=margin_gap,
            threshold="毛利率与同业中位数绝对偏离 > 5个百分点",
            triggered=margin_gap is not None and abs(margin_gap) > 0.05,
            observation=f"毛利率较同业中位数偏离 {margin_gap:.2%}。"
            if margin_gap is not None
            else "未提供同业毛利率基准。",
            interpretation="异常高低均需结合产品结构、会计口径和成本归集解释。",
            evidence_ids=current.evidence_ids,
            action=_action(
                "业务财务 / 成本管理负责人",
                "60天",
                ["统一同业口径后重算", "建立产品级毛利桥接"],
                ["产品毛利率", "价格与成本差异", "同业口径差异"],
            ),
            weight=10,
        ),
        _signal(
            signal_id="FR-NONRECURRING",
            category=FinancialRiskCategory.EARNINGS_QUALITY,
            label="非经常性损益依赖",
            value=non_recurring_ratio,
            threshold="非经常性损益绝对值/净利润 > 30%",
            triggered=(non_recurring_ratio is not None and non_recurring_ratio > 0.30),
            observation=f"非经常性损益占净利润 {non_recurring_ratio:.2%}。"
            if non_recurring_ratio is not None
            else "净利润为零，无法计算非经常性损益依赖度。",
            interpretation="利润对一次性项目的依赖可能削弱持续经营表现的可比性。",
            evidence_ids=current.evidence_ids,
            action=_action(
                "财务报告负责人",
                "30天",
                ["区分经常性与一次性利润来源", "建立调整后利润口径"],
                ["扣非净利润", "非经常性损益占比"],
            ),
            weight=10,
        ),
        _signal(
            signal_id="FR-CURRENT-RATIO",
            category=FinancialRiskCategory.LIQUIDITY,
            label="短期流动性覆盖",
            value=current_ratio,
            threshold="流动比率 < 1.00",
            triggered=current_ratio is not None and current_ratio < 1.0,
            observation=f"流动比率为 {current_ratio:.2f}。"
            if current_ratio is not None
            else "流动负债为零，流动比率不适用。",
            interpretation="流动资产对短期负债的账面覆盖不足，需要滚动现金预测。",
            evidence_ids=current.evidence_ids,
            action=_action(
                "资金管理负责人",
                "14天",
                ["建立13周滚动现金流预测", "复核授信与债务到期结构"],
                ["最低现金余额", "未来90天到期债务覆盖率"],
            ),
            weight=12,
        ),
        _signal(
            signal_id="FR-NET-DEBT-CFO",
            category=FinancialRiskCategory.LIQUIDITY,
            label="净债务现金偿付压力",
            value=net_debt_to_cfo,
            threshold="净债务/经营现金流 > 3.00，或经营现金流非正且存在净债务",
            triggered=(
                (net_debt_to_cfo is not None and net_debt_to_cfo > 3)
                or (net_debt > 0 and current.operating_cash_flow <= 0)
            ),
            observation=f"净债务/经营现金流为 {net_debt_to_cfo:.2f}。"
            if net_debt_to_cfo is not None
            else "存在净债务且经营现金流不能提供正向覆盖。",
            interpretation="债务偿付对再融资或资产处置的依赖可能上升。",
            evidence_ids=current.evidence_ids,
            action=_action(
                "CFO / 资金管理负责人",
                "30天",
                ["开展债务到期压力测试", "制定备用流动性方案"],
                ["净债务/经营现金流", "未使用授信额度"],
            ),
            weight=8,
        ),
        _signal(
            signal_id="FR-AUDIT-OPINION",
            category=FinancialRiskCategory.GOVERNANCE,
            label="审计意见异常",
            value=None,
            threshold="审计意见不是标准无保留意见",
            triggered=data.audit_opinion.casefold() != "standard_unqualified",
            observation=f"登记审计意见：{data.audit_opinion}。",
            interpretation="非标准意见需要逐项追踪审计事项及管理层整改。",
            evidence_ids=current.evidence_ids,
            action=_action(
                "审计委员会 / 财务负责人",
                "立即纳入审计委员会议程",
                ["取得完整审计报告", "建立审计事项整改台账"],
                ["未关闭审计事项", "整改逾期数量"],
            ),
            weight=15,
        ),
        _signal(
            signal_id="FR-EXCHANGE-INQUIRY",
            category=FinancialRiskCategory.REGULATORY,
            label="交易所问询",
            value=float(data.exchange_inquiry_count),
            threshold="截止日内交易所问询数量 > 0",
            triggered=data.exchange_inquiry_count > 0,
            observation=f"登记交易所问询 {data.exchange_inquiry_count} 项。",
            interpretation="问询本身不代表违规，但相关事项应纳入证据补充和持续监控。",
            evidence_ids=current.evidence_ids,
            action=_action(
                "董事会秘书 / 内控负责人",
                "按监管时限",
                ["核对问询事项与回复证据", "跟踪后续监管动作"],
                ["未回复问询数量", "重复问询事项"],
            ),
            weight=4,
        ),
        _signal(
            signal_id="FR-REGULATORY-PENALTY",
            category=FinancialRiskCategory.REGULATORY,
            label="监管处罚记录",
            value=float(data.regulatory_penalty_count),
            threshold="截止日内监管处罚数量 > 0",
            triggered=data.regulatory_penalty_count > 0,
            observation=f"登记监管处罚 {data.regulatory_penalty_count} 项。",
            interpretation="已确认处罚需要映射至控制缺陷、责任主体和整改进度。",
            evidence_ids=current.evidence_ids,
            action=_action(
                "首席合规官 / 审计委员会",
                "30天",
                ["形成处罚事项根因分析", "验证整改措施有效性"],
                ["整改完成率", "同类问题复发次数"],
            ),
            weight=8,
        ),
    ]
    maximum = sum(signal.weight for signal in signals)
    triggered_weight = sum(signal.weight for signal in signals if signal.triggered)
    score = round(triggered_weight / maximum * 100, 1)
    if score >= 70:
        level = FinancialRiskLevel.CRITICAL
    elif score >= 40:
        level = FinancialRiskLevel.HIGH
    elif score >= 20:
        level = FinancialRiskLevel.MODERATE
    else:
        level = FinancialRiskLevel.LOW
    warnings = [
        "This scorecard identifies screening signals, not fraud or audit conclusions.",
        "Thresholds are transparent portfolio-demo rules and require sector calibration.",
    ]
    if data.peer_gross_margin_median is None:
        warnings.append("Peer gross-margin benchmark was unavailable.")
    return FinancialRiskScorecard(
        company_name=data.company_name,
        security_code=data.security_code,
        as_of_date=data.as_of_date,
        risk_score=score,
        risk_level=level,
        signals=signals,
        reason_codes=[signal.signal_id for signal in signals if signal.triggered],
        warnings=warnings,
        methodology_version=METHODOLOGY_VERSION,
    )


def _hash_payload(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_audit_trail(
    data: FinancialRiskInput,
    scorecard: FinancialRiskScorecard,
    *,
    code_version: str,
    run_id: str | None = None,
) -> AuditTrail:
    return AuditTrail(
        run_id=run_id or uuid4().hex,
        generated_at=datetime.now(UTC),
        code_version=code_version,
        methodology_version=scorecard.methodology_version,
        input_hash=_hash_payload(data.model_dump(mode="json")),
        output_hash=_hash_payload(scorecard.model_dump(mode="json")),
    )


def payload_hash(payload: Any) -> str:
    """Expose the canonical hash for independent quality-review reproduction."""
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump(mode="json")
    return _hash_payload(payload)
