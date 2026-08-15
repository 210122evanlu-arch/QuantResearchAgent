"""Deterministic and explainable financial-anomaly screening."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from schemas.enums import (
    AuditOpinionStatus,
    FinancialRiskCategory,
    FinancialRiskLevel,
    IssueSeverity,
)
from schemas.financial_risk import (
    AuditTrail,
    FinancialRiskInput,
    FinancialRiskScorecard,
    FinancialRiskSignal,
    RiskAction,
)
from tools.financial_risk_thresholds import get_financial_risk_thresholds

METHODOLOGY_VERSION = "financial-risk-scorecard-2.0"


def _growth(current: float, prior: float) -> float | None:
    if prior == 0:
        return None
    return current / prior - 1


def _calculated_growth(current: float | None, prior: float | None) -> float | None:
    if current is None or prior is None:
        return None
    return _growth(current, prior)


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
    available: bool = True,
) -> FinancialRiskSignal:
    return FinancialRiskSignal(
        signal_id=signal_id,
        category=category,
        label=label,
        value=value,
        threshold=threshold,
        available=available,
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
    thresholds = get_financial_risk_thresholds(data.industry_profile)
    evidence_ids = list(dict.fromkeys([*current.evidence_ids, *prior.evidence_ids]))
    revenue_growth = current.revenue_growth
    if revenue_growth is None:
        revenue_growth = _calculated_growth(current.revenue, prior.revenue)
    receivable_growth = current.accounts_receivable_growth
    if receivable_growth is None:
        receivable_growth = _calculated_growth(
            current.accounts_receivable, prior.accounts_receivable
        )
    inventory_growth = current.inventory_growth
    if inventory_growth is None:
        inventory_growth = _calculated_growth(current.inventory, prior.inventory)
    cash_conversion = current.cash_conversion_ratio
    if (
        cash_conversion is None
        and current.operating_cash_flow is not None
        and current.net_profit is not None
        and current.net_profit > 0
    ):
        cash_conversion = current.operating_cash_flow / current.net_profit
    accrual_ratio = None
    if (
        current.net_profit is not None
        and current.operating_cash_flow is not None
        and current.total_assets is not None
    ):
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
        if current.gross_margin is not None
        and data.peer_gross_margin_median is not None
        else None
    )
    non_recurring_ratio = (
        abs(current.non_recurring_profit) / abs(current.net_profit)
        if current.non_recurring_profit is not None
        and current.net_profit is not None
        and current.net_profit != 0
        else None
    )
    current_ratio = current.current_ratio
    if (
        current_ratio is None
        and current.current_assets is not None
        and current.current_liabilities is not None
        and current.current_liabilities > 0
    ):
        current_ratio = current.current_assets / current.current_liabilities
    net_debt_to_cfo = current.net_debt_to_operating_cash_flow
    net_debt = None
    if (
        current.interest_bearing_debt is not None
        and current.cash_and_equivalents is not None
    ):
        net_debt = current.interest_bearing_debt - current.cash_and_equivalents
    if (
        net_debt_to_cfo is None
        and net_debt is not None
        and current.operating_cash_flow is not None
        and current.operating_cash_flow > 0
    ):
        net_debt_to_cfo = net_debt / current.operating_cash_flow
    roe_decline = (
        prior.return_on_equity - current.return_on_equity
        if prior.return_on_equity is not None and current.return_on_equity is not None
        else None
    )
    margin_decline = (
        prior.net_profit_margin - current.net_profit_margin
        if prior.net_profit_margin is not None and current.net_profit_margin is not None
        else None
    )
    receivable_days_growth = _calculated_growth(
        current.receivables_days, prior.receivables_days
    )
    inventory_days_growth = _calculated_growth(
        current.inventory_days, prior.inventory_days
    )
    asset_turnover_decline = (
        1 - current.asset_turnover / prior.asset_turnover
        if current.asset_turnover is not None
        and prior.asset_turnover is not None
        and prior.asset_turnover > 0
        else None
    )

    signals = [
        _signal(
            signal_id="FR-CASH-CONVERSION",
            category=FinancialRiskCategory.EARNINGS_QUALITY,
            label="利润现金转化",
            value=cash_conversion,
            threshold=f"经营现金流/净利润 < {thresholds.cash_conversion_min:.2f}",
            triggered=(
                cash_conversion is not None
                and cash_conversion < thresholds.cash_conversion_min
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
            available=cash_conversion is not None,
        ),
        _signal(
            signal_id="FR-ACCRUAL",
            category=FinancialRiskCategory.EARNINGS_QUALITY,
            label="应计利润压力",
            value=accrual_ratio,
            threshold=f"(净利润-经营现金流)/总资产 > {thresholds.accrual_ratio_max:.0%}",
            triggered=(
                accrual_ratio is not None
                and accrual_ratio > thresholds.accrual_ratio_max
            ),
            observation=(
                f"应计利润比率为 {accrual_ratio:.2%}。"
                if accrual_ratio is not None
                else "缺少净利润、经营现金流或总资产，无法计算应计利润比率。"
            ),
            interpretation="较高应计项目可能降低盈利质量，需核对形成原因。",
            evidence_ids=evidence_ids,
            action=_action(
                "财务总监 / 内控负责人",
                "45天",
                ["按科目拆解应计项目", "抽查重大期末调整分录"],
                ["应计利润比率", "重大调整分录数量"],
            ),
            weight=10,
            available=accrual_ratio is not None,
        ),
        _signal(
            signal_id="FR-AR-GAP",
            category=FinancialRiskCategory.WORKING_CAPITAL,
            label="应收增速偏离收入",
            value=ar_gap,
            threshold=(
                f"应收账款增速－收入增速 > {thresholds.receivable_growth_gap_max:.0%}"
            ),
            triggered=(
                ar_gap is not None and ar_gap > thresholds.receivable_growth_gap_max
            ),
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
            available=ar_gap is not None,
        ),
        _signal(
            signal_id="FR-INVENTORY-GAP",
            category=FinancialRiskCategory.WORKING_CAPITAL,
            label="存货增速偏离收入",
            value=inventory_gap,
            threshold=(
                f"存货增速－收入增速 > {thresholds.inventory_growth_gap_max:.0%}"
            ),
            triggered=(
                inventory_gap is not None
                and inventory_gap > thresholds.inventory_growth_gap_max
            ),
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
            available=inventory_gap is not None,
        ),
        _signal(
            signal_id="FR-MARGIN-PEER",
            category=FinancialRiskCategory.MARGIN,
            label="毛利率同业偏离",
            value=margin_gap,
            threshold=(
                "毛利率与同业中位数绝对偏离 > "
                f"{thresholds.gross_margin_deviation_max:.0%}"
            ),
            triggered=(
                margin_gap is not None
                and abs(margin_gap) > thresholds.gross_margin_deviation_max
            ),
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
            available=margin_gap is not None,
        ),
        _signal(
            signal_id="FR-NONRECURRING",
            category=FinancialRiskCategory.EARNINGS_QUALITY,
            label="非经常性损益依赖",
            value=non_recurring_ratio,
            threshold=(
                "非经常性损益绝对值/净利润 > "
                f"{thresholds.non_recurring_profit_ratio_max:.0%}"
            ),
            triggered=(
                non_recurring_ratio is not None
                and non_recurring_ratio > thresholds.non_recurring_profit_ratio_max
            ),
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
            available=non_recurring_ratio is not None,
        ),
        _signal(
            signal_id="FR-CURRENT-RATIO",
            category=FinancialRiskCategory.LIQUIDITY,
            label="短期流动性覆盖",
            value=current_ratio,
            threshold=f"流动比率 < {thresholds.current_ratio_min:.2f}",
            triggered=(
                current_ratio is not None
                and current_ratio < thresholds.current_ratio_min
            ),
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
            available=current_ratio is not None,
        ),
        _signal(
            signal_id="FR-NET-DEBT-CFO",
            category=FinancialRiskCategory.LIQUIDITY,
            label="净债务现金偿付压力",
            value=net_debt_to_cfo,
            threshold=f"净债务/经营现金流 > {thresholds.net_debt_to_cfo_max:.2f}",
            triggered=(
                net_debt_to_cfo is not None
                and net_debt_to_cfo > thresholds.net_debt_to_cfo_max
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
            available=net_debt_to_cfo is not None,
        ),
        _signal(
            signal_id="FR-DEBT-ASSETS",
            category=FinancialRiskCategory.LIQUIDITY,
            label="资产负债率压力",
            value=current.debt_to_assets,
            threshold=f"资产负债率 > {thresholds.debt_to_assets_max:.0%}",
            triggered=(
                current.debt_to_assets is not None
                and current.debt_to_assets > thresholds.debt_to_assets_max
            ),
            observation=(
                f"资产负债率为 {current.debt_to_assets:.2%}。"
                if current.debt_to_assets is not None
                else "未取得资产负债率。"
            ),
            interpretation="杠杆水平较高会降低盈利或融资环境恶化时的缓冲空间。",
            evidence_ids=current.evidence_ids,
            action=_action(
                "CFO / 资金管理负责人",
                "30天",
                ["分期限拆解有息与经营负债", "建立杠杆下降情景"],
                ["资产负债率", "净债务率", "未来一年到期债务"],
            ),
            weight=10,
            available=current.debt_to_assets is not None,
        ),
        _signal(
            signal_id="FR-INTEREST-COVERAGE",
            category=FinancialRiskCategory.LIQUIDITY,
            label="利息保障能力",
            value=current.interest_coverage,
            threshold=f"EBIT/利息费用 < {thresholds.interest_coverage_min:.2f}",
            triggered=(
                current.interest_coverage is not None
                and current.interest_coverage < thresholds.interest_coverage_min
            ),
            observation=(
                f"利息保障倍数为 {current.interest_coverage:.2f}。"
                if current.interest_coverage is not None
                else "未取得利息保障倍数。"
            ),
            interpretation="经营利润对利息支出的覆盖偏弱，偿债弹性需要压力测试。",
            evidence_ids=current.evidence_ids,
            action=_action(
                "资金管理负责人",
                "30天",
                ["测算不同盈利情景下的利息覆盖", "复核融资成本和契约条款"],
                ["利息保障倍数", "平均融资成本", "契约余量"],
            ),
            weight=10,
            available=current.interest_coverage is not None,
        ),
        _signal(
            signal_id="FR-ROE-DECLINE",
            category=FinancialRiskCategory.EARNINGS_QUALITY,
            label="资本回报下滑",
            value=roe_decline,
            threshold=f"ROE同比下降 > {thresholds.roe_decline_max:.0%}",
            triggered=(
                roe_decline is not None and roe_decline > thresholds.roe_decline_max
            ),
            observation=(
                f"ROE同比下降 {roe_decline:.2%}。"
                if roe_decline is not None
                else "缺少可比两期ROE。"
            ),
            interpretation="资本回报下降需要区分利润率、周转率和杠杆贡献。",
            evidence_ids=evidence_ids,
            action=_action(
                "CFO / 战略规划负责人",
                "45天",
                ["建立杜邦分析桥接", "明确低效资本整改清单"],
                ["ROE", "ROIC", "资产周转率"],
            ),
            weight=8,
            available=roe_decline is not None,
        ),
        _signal(
            signal_id="FR-MARGIN-DECLINE",
            category=FinancialRiskCategory.EARNINGS_QUALITY,
            label="净利率下滑",
            value=margin_decline,
            threshold=f"净利率同比下降 > {thresholds.net_margin_decline_max:.0%}",
            triggered=(
                margin_decline is not None
                and margin_decline > thresholds.net_margin_decline_max
            ),
            observation=(
                f"净利率同比下降 {margin_decline:.2%}。"
                if margin_decline is not None
                else "缺少可比两期净利率。"
            ),
            interpretation="净利率收缩可能来自价格、成本、费用或一次性项目变化。",
            evidence_ids=evidence_ids,
            action=_action(
                "业务财务负责人",
                "30天",
                ["建立价格成本费用桥接", "区分结构性与一次性影响"],
                ["净利率", "期间费用率", "单位贡献利润"],
            ),
            weight=8,
            available=margin_decline is not None,
        ),
        _signal(
            signal_id="FR-AR-DAYS",
            category=FinancialRiskCategory.WORKING_CAPITAL,
            label="应收周转天数恶化",
            value=receivable_days_growth,
            threshold=(
                f"应收周转天数同比增长 > {thresholds.receivable_days_growth_max:.0%}"
            ),
            triggered=(
                receivable_days_growth is not None
                and receivable_days_growth > thresholds.receivable_days_growth_max
            ),
            observation=(
                f"应收周转天数同比增长 {receivable_days_growth:.2%}。"
                if receivable_days_growth is not None
                else "缺少可比两期应收周转天数。"
            ),
            interpretation="回款周期拉长可能增加坏账和现金占用。",
            evidence_ids=evidence_ids,
            action=_action(
                "信用管理负责人",
                "30天",
                ["穿透客户账龄和期后回款", "调整信用额度"],
                ["应收周转天数", "逾期率", "坏账覆盖率"],
            ),
            weight=8,
            available=receivable_days_growth is not None,
        ),
        _signal(
            signal_id="FR-INVENTORY-DAYS",
            category=FinancialRiskCategory.WORKING_CAPITAL,
            label="存货周转天数恶化",
            value=inventory_days_growth,
            threshold=(
                f"存货周转天数同比增长 > {thresholds.inventory_days_growth_max:.0%}"
            ),
            triggered=(
                inventory_days_growth is not None
                and inventory_days_growth > thresholds.inventory_days_growth_max
            ),
            observation=(
                f"存货周转天数同比增长 {inventory_days_growth:.2%}。"
                if inventory_days_growth is not None
                else "缺少可比两期存货周转天数。"
            ),
            interpretation="库存消化放缓可能增加价格折让和减值风险。",
            evidence_ids=evidence_ids,
            action=_action(
                "供应链负责人",
                "45天",
                ["分产品分析库龄和动销", "设置清库存与减值方案"],
                ["存货周转天数", "滞销库存占比", "减值率"],
            ),
            weight=8,
            available=inventory_days_growth is not None,
        ),
        _signal(
            signal_id="FR-ASSET-TURNOVER",
            category=FinancialRiskCategory.EARNINGS_QUALITY,
            label="资产周转效率下降",
            value=asset_turnover_decline,
            threshold=(
                f"资产周转率同比下降 > {thresholds.asset_turnover_decline_max:.0%}"
            ),
            triggered=(
                asset_turnover_decline is not None
                and asset_turnover_decline > thresholds.asset_turnover_decline_max
            ),
            observation=(
                f"资产周转率同比下降 {asset_turnover_decline:.2%}。"
                if asset_turnover_decline is not None
                else "缺少可比两期资产周转率。"
            ),
            interpretation="资产扩张未同步转化为收入，需检查产能利用和资本效率。",
            evidence_ids=evidence_ids,
            action=_action(
                "运营负责人 / CFO",
                "60天",
                ["按资产单元评估利用率", "暂停低回报资本开支"],
                ["资产周转率", "产能利用率", "新增资本回报"],
            ),
            weight=6,
            available=asset_turnover_decline is not None,
        ),
        _signal(
            signal_id="FR-IMPAIRMENT",
            category=FinancialRiskCategory.EARNINGS_QUALITY,
            label="资产减值压力",
            value=current.impairment_to_assets,
            threshold=f"资产减值/总资产 > {thresholds.impairment_to_assets_max:.0%}",
            triggered=(
                current.impairment_to_assets is not None
                and current.impairment_to_assets > thresholds.impairment_to_assets_max
            ),
            observation=(
                f"资产减值占总资产 {current.impairment_to_assets:.2%}。"
                if current.impairment_to_assets is not None
                else "未取得资产减值占比。"
            ),
            interpretation="较高减值可能反映资产质量或历史估计调整压力。",
            evidence_ids=current.evidence_ids,
            action=_action(
                "财务报告负责人 / 审计委员会",
                "45天",
                ["复核减值模型与关键假设", "开展敏感性分析"],
                ["减值/总资产", "预测偏差", "减值覆盖率"],
            ),
            weight=10,
            available=current.impairment_to_assets is not None,
        ),
        _signal(
            signal_id="FR-GOODWILL",
            category=FinancialRiskCategory.EARNINGS_QUALITY,
            label="商誉敞口",
            value=current.goodwill_to_assets,
            threshold=f"商誉/总资产 > {thresholds.goodwill_to_assets_max:.0%}",
            triggered=(
                current.goodwill_to_assets is not None
                and current.goodwill_to_assets > thresholds.goodwill_to_assets_max
            ),
            observation=(
                f"商誉占总资产 {current.goodwill_to_assets:.2%}。"
                if current.goodwill_to_assets is not None
                else "未取得商誉占比。"
            ),
            interpretation="商誉占比较高会放大并购标的未达预期时的减值影响。",
            evidence_ids=current.evidence_ids,
            action=_action(
                "投资管理负责人 / CFO",
                "60天",
                ["逐项复核并购假设", "建立标的业绩预警"],
                ["商誉/总资产", "标的预算达成率", "减值敏感性"],
            ),
            weight=8,
            available=current.goodwill_to_assets is not None,
        ),
        _signal(
            signal_id="FR-RELATED-PARTY",
            category=FinancialRiskCategory.GOVERNANCE,
            label="关联交易集中度",
            value=current.related_party_transaction_ratio,
            threshold=f"关联交易/收入 > {thresholds.related_party_ratio_max:.0%}",
            triggered=(
                current.related_party_transaction_ratio is not None
                and current.related_party_transaction_ratio
                > thresholds.related_party_ratio_max
            ),
            observation=(
                f"关联交易占收入 {current.related_party_transaction_ratio:.2%}。"
                if current.related_party_transaction_ratio is not None
                else "未取得关联交易占比。"
            ),
            interpretation="关联交易集中需要核验商业必要性、定价公允性和审批程序。",
            evidence_ids=current.evidence_ids,
            action=_action(
                "董事会秘书 / 内控负责人",
                "60天",
                ["执行非关联价格对标", "复核审批与披露完整性"],
                ["关联交易占比", "价格偏离率", "未审批交易数量"],
            ),
            weight=8,
            available=current.related_party_transaction_ratio is not None,
        ),
        _signal(
            signal_id="FR-CUSTOMER-CONCENTRATION",
            category=FinancialRiskCategory.GOVERNANCE,
            label="客户集中度",
            value=current.top_five_customer_concentration,
            threshold=(
                f"前五大客户收入占比 > {thresholds.customer_concentration_max:.0%}"
            ),
            triggered=(
                current.top_five_customer_concentration is not None
                and current.top_five_customer_concentration
                > thresholds.customer_concentration_max
            ),
            observation=(
                f"前五大客户收入占比 {current.top_five_customer_concentration:.2%}。"
                if current.top_five_customer_concentration is not None
                else "未取得前五大客户集中度。"
            ),
            interpretation="客户集中可能放大单一客户流失、议价和信用风险。",
            evidence_ids=current.evidence_ids,
            action=_action(
                "销售负责人 / 信用管理负责人",
                "60天",
                ["制定客户分散计划", "对核心客户进行信用压力测试"],
                ["前五大客户占比", "核心客户续约率", "客户信用敞口"],
            ),
            weight=6,
            available=current.top_five_customer_concentration is not None,
        ),
        _signal(
            signal_id="FR-SUPPLIER-CONCENTRATION",
            category=FinancialRiskCategory.GOVERNANCE,
            label="供应商集中度",
            value=current.top_five_supplier_concentration,
            threshold=(
                f"前五大供应商采购占比 > {thresholds.supplier_concentration_max:.0%}"
            ),
            triggered=(
                current.top_five_supplier_concentration is not None
                and current.top_five_supplier_concentration
                > thresholds.supplier_concentration_max
            ),
            observation=(
                f"前五大供应商采购占比 {current.top_five_supplier_concentration:.2%}。"
                if current.top_five_supplier_concentration is not None
                else "未取得前五大供应商集中度。"
            ),
            interpretation="供应商集中可能带来断供、价格和替代成本风险。",
            evidence_ids=current.evidence_ids,
            action=_action(
                "采购负责人 / 供应链负责人",
                "90天",
                ["建立关键物料双供策略", "评估替代供应商切换时间"],
                ["前五大供应商占比", "双供覆盖率", "替代周期"],
            ),
            weight=6,
            available=current.top_five_supplier_concentration is not None,
        ),
        _signal(
            signal_id="FR-RD-CAPITALIZATION",
            category=FinancialRiskCategory.EARNINGS_QUALITY,
            label="研发资本化比例",
            value=current.rd_capitalization_ratio,
            threshold=(
                f"研发资本化比例 > {thresholds.rd_capitalization_ratio_max:.0%}"
            ),
            triggered=(
                current.rd_capitalization_ratio is not None
                and current.rd_capitalization_ratio
                > thresholds.rd_capitalization_ratio_max
            ),
            observation=(
                f"研发资本化比例 {current.rd_capitalization_ratio:.2%}。"
                if current.rd_capitalization_ratio is not None
                else "未取得研发资本化比例。"
            ),
            interpretation="较高资本化比例需要核验确认条件、项目进度和减值测试。",
            evidence_ids=current.evidence_ids,
            action=_action(
                "研发财务负责人 / 审计委员会",
                "45天",
                ["抽查资本化项目证据", "比较同业会计政策"],
                ["研发资本化率", "项目转固周期", "研发资产减值率"],
            ),
            weight=8,
            available=current.rd_capitalization_ratio is not None,
        ),
        _signal(
            signal_id="FR-AUDIT-OPINION",
            category=FinancialRiskCategory.GOVERNANCE,
            label="审计意见异常",
            value=None,
            threshold="审计意见不是标准无保留意见",
            triggered=data.audit_opinion == AuditOpinionStatus.NON_STANDARD,
            observation=f"登记审计意见：{data.audit_opinion.value}。",
            interpretation="非标准意见需要逐项追踪审计事项及管理层整改。",
            evidence_ids=(data.audit_opinion_evidence_ids or current.evidence_ids),
            action=_action(
                "审计委员会 / 财务负责人",
                "立即纳入审计委员会议程",
                ["取得完整审计报告", "建立审计事项整改台账"],
                ["未关闭审计事项", "整改逾期数量"],
            ),
            weight=15,
            available=data.audit_opinion != AuditOpinionStatus.UNKNOWN,
        ),
        _signal(
            signal_id="FR-EXCHANGE-INQUIRY",
            category=FinancialRiskCategory.REGULATORY,
            label="交易所问询相关披露",
            value=float(data.exchange_inquiry_count),
            threshold="截止日内问询相关披露数量 > 0",
            triggered=data.exchange_inquiry_count > 0,
            observation=f"登记问询相关披露 {data.exchange_inquiry_count} 项。",
            interpretation="问询本身不代表违规，但相关事项应纳入证据补充和持续监控。",
            evidence_ids=(data.exchange_inquiry_evidence_ids or current.evidence_ids),
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
            label="监管处罚及措施",
            value=float(data.regulatory_penalty_count),
            threshold="截止日内已确认监管处罚或措施相关披露数量 > 0",
            triggered=data.regulatory_penalty_count > 0,
            observation=f"登记已确认监管处罚或措施相关披露 {data.regulatory_penalty_count} 项。",
            interpretation="已确认处罚需要映射至控制缺陷、责任主体和整改进度。",
            evidence_ids=(data.regulatory_penalty_evidence_ids or current.evidence_ids),
            action=_action(
                "首席合规官 / 审计委员会",
                "30天",
                ["形成处罚事项根因分析", "验证整改措施有效性"],
                ["整改完成率", "同类问题复发次数"],
            ),
            weight=8,
        ),
    ]
    total_weight = sum(signal.weight for signal in signals)
    available_weight = sum(signal.weight for signal in signals if signal.available)
    triggered_weight = sum(
        signal.weight for signal in signals if signal.available and signal.triggered
    )
    score = (
        round(triggered_weight / available_weight * 100, 1) if available_weight else 0
    )
    data_coverage = available_weight / total_weight
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
        "Thresholds are transparent industry profiles and require professional validation.",
        *data.data_warnings,
    ]
    if data.peer_gross_margin_median is None:
        warnings.append("Peer gross-margin benchmark was unavailable.")
    if data.audit_opinion == AuditOpinionStatus.UNKNOWN:
        warnings.append(
            "Audit opinion status was not confirmed from full-text evidence."
        )
    if data_coverage < 0.6:
        warnings.append(
            "Weighted data coverage is below 60%; do not compare the composite score across companies."
        )
    return FinancialRiskScorecard(
        company_name=data.company_name,
        security_code=data.security_code,
        as_of_date=data.as_of_date,
        risk_score=score,
        risk_level=level,
        data_coverage=data_coverage,
        signals=signals,
        reason_codes=[signal.signal_id for signal in signals if signal.triggered],
        warnings=warnings,
        methodology_version=METHODOLOGY_VERSION,
        threshold_profile=(f"{data.industry_profile.value}/{thresholds.version}"),
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
