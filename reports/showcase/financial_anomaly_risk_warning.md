# 示例智造股份有限公司（DEMO001）财务异常识别与风险预警报告

| 报告属性 | 内容 |
| --- | --- |
| 截止日期 | 2026-04-30 |
| 交付状态 | IQR passed / 人工签署待定 |
| 风险评分 | 71.1 / 100 |
| 风险等级 | `critical` |
| 触发信号 | 8 / 11 |
| 方法版本 | financial-risk-scorecard-1.0 |

> 本报告用于财务异常筛查和管理层风险预警，不构成审计意见、舞弊认定、信用评级或投资建议。异常信号必须结合原始凭证、业务访谈和专业人员复核。

## 执行摘要

规则引擎识别出 8 项触发信号，综合风险评分为 71.1，等级为 `critical`。该结果表示需要进一步核验的财务与治理信号，不表示公司存在财务舞弊。

**管理层优先事项：** 利润现金转化、应收增速偏离收入、存货增速偏离收入、毛利率同业偏离

## 财务异常风险信号

| 原因代码 | 类别 | 指标 | 数值 | 阈值 | 严重程度 |
| --- | --- | --- | ---: | --- | --- |
| FR-CASH-CONVERSION | earnings_quality | 利润现金转化 | 0.41x | 经营现金流/净利润 < 0.80，或盈利但经营现金流为负 | critical |
| FR-ACCRUAL | earnings_quality | 应计利润压力 | 3.80% | (净利润-经营现金流)/总资产 > 0.10 | not_triggered |
| FR-AR-GAP | working_capital | 应收增速偏离收入 | 55.16% | 应收账款增速－收入增速 > 15个百分点 | high |
| FR-INVENTORY-GAP | working_capital | 存货增速偏离收入 | 44.78% | 存货增速－收入增速 > 15个百分点 | high |
| FR-MARGIN-PEER | margin | 毛利率同业偏离 | 7.50% | 毛利率与同业中位数绝对偏离 > 5个百分点 | high |
| FR-NONRECURRING | earnings_quality | 非经常性损益依赖 | 39.13% | 非经常性损益绝对值/净利润 > 30% | high |
| FR-CURRENT-RATIO | liquidity | 短期流动性覆盖 | 0.89x | 流动比率 < 1.00 | high |
| FR-NET-DEBT-CFO | liquidity | 净债务现金偿付压力 | 8.03x | 净债务/经营现金流 > 3.00，或经营现金流非正且存在净债务 | medium |
| FR-AUDIT-OPINION | governance | 审计意见异常 | 不适用 | 审计意见不是标准无保留意见 | not_triggered |
| FR-EXCHANGE-INQUIRY | regulatory | 交易所问询 | 1 | 截止日内交易所问询数量 > 0 | medium |
| FR-REGULATORY-PENALTY | regulatory | 监管处罚记录 | 0 | 截止日内监管处罚数量 > 0 | not_triggered |

### 触发信号解释

#### 利润现金转化｜FR-CASH-CONVERSION

- **事实观察：** 经营现金流/净利润为 0.41。
- **风险推断：** 利润与现金回收背离，需要拆解营运资本和非现金项目。
- **证据：** DEMO-FR-E1, DEMO-FR-E2

#### 应收增速偏离收入｜FR-AR-GAP

- **事实观察：** 应收账款增速较收入增速高 55.16%。
- **风险推断：** 回款节奏可能弱于收入确认，需要核对账龄和客户集中度。
- **证据：** DEMO-FR-E1, DEMO-FR-E2

#### 存货增速偏离收入｜FR-INVENTORY-GAP

- **事实观察：** 存货增速较收入增速高 44.78%。
- **风险推断：** 库存积压或减值压力可能上升，需要结合库龄和订单验证。
- **证据：** DEMO-FR-E1, DEMO-FR-E2

#### 毛利率同业偏离｜FR-MARGIN-PEER

- **事实观察：** 毛利率较同业中位数偏离 7.50%。
- **风险推断：** 异常高低均需结合产品结构、会计口径和成本归集解释。
- **证据：** DEMO-FR-E1

#### 非经常性损益依赖｜FR-NONRECURRING

- **事实观察：** 非经常性损益占净利润 39.13%。
- **风险推断：** 利润对一次性项目的依赖可能削弱持续经营表现的可比性。
- **证据：** DEMO-FR-E1

#### 短期流动性覆盖｜FR-CURRENT-RATIO

- **事实观察：** 流动比率为 0.89。
- **风险推断：** 流动资产对短期负债的账面覆盖不足，需要滚动现金预测。
- **证据：** DEMO-FR-E1

#### 净债务现金偿付压力｜FR-NET-DEBT-CFO

- **事实观察：** 净债务/经营现金流为 8.03。
- **风险推断：** 债务偿付对再融资或资产处置的依赖可能上升。
- **证据：** DEMO-FR-E1

#### 交易所问询｜FR-EXCHANGE-INQUIRY

- **事实观察：** 登记交易所问询 1 项。
- **风险推断：** 问询本身不代表违规，但相关事项应纳入证据补充和持续监控。
- **证据：** DEMO-FR-E1

## 管理行动路线

| 风险信号 | Owner | Timeline | 建议动作 | KPI / 验证标准 |
| --- | --- | --- | --- | --- |
| 利润现金转化 | CFO / 财务规划与分析 | 30天 | 建立利润到经营现金流桥接表；复核大额非现金损益 | 经营现金流/净利润；自由现金流 |
| 应收增速偏离收入 | 销售财务 / 信用管理负责人 | 30天 | 开展客户与账龄穿透；复核期后回款 | 逾期应收占比；期后回款率；前五大客户集中度 |
| 存货增速偏离收入 | 供应链负责人 / 财务总监 | 45天 | 按产品和库龄拆解存货；对滞销品执行减值压力测试 | 存货周转天数；一年以上库龄占比；减值覆盖率 |
| 毛利率同业偏离 | 业务财务 / 成本管理负责人 | 60天 | 统一同业口径后重算；建立产品级毛利桥接 | 产品毛利率；价格与成本差异；同业口径差异 |
| 非经常性损益依赖 | 财务报告负责人 | 30天 | 区分经常性与一次性利润来源；建立调整后利润口径 | 扣非净利润；非经常性损益占比 |
| 短期流动性覆盖 | 资金管理负责人 | 14天 | 建立13周滚动现金流预测；复核授信与债务到期结构 | 最低现金余额；未来90天到期债务覆盖率 |
| 净债务现金偿付压力 | CFO / 资金管理负责人 | 30天 | 开展债务到期压力测试；制定备用流动性方案 | 净债务/经营现金流；未使用授信额度 |
| 交易所问询 | 董事会秘书 / 内控负责人 | 按监管时限 | 核对问询事项与回复证据；跟踪后续监管动作 | 未回复问询数量；重复问询事项 |

## 事实、推断与建议边界

- **事实：** 指标由登记的两期结构化财务数据及监管计数计算。
- **推断：** 阈值触发只说明需要进一步核验，不证明会计处理不当。
- **建议：** Owner、Timeline 和 KPI 是管理建议，需要客户确认后执行。
- **数据范围：** 本案例为可公开分发的合成财务夹具，不对应任何真实上市公司；用于验证指标、路由、质量复核和报告契约。
- **方法边界：** 当前阈值为透明规则，需要根据行业、会计准则和历史样本校准。

## 内部质量复核

- 决策：`passed`
- 控制通过：8/8
- 证据覆盖率：100.0%
- 可复现：True
- 报告一致：True
- 结论：Automated engagement-quality controls passed; human sign-off remains required.

| 控制编号 | 类别 | 结果 | 说明 |
| --- | --- | --- | --- |
| IQR-EVIDENCE-CUTOFF | evidence | PASS | No post-cutoff evidence detected. |
| IQR-EVIDENCE-LINEAGE | evidence | PASS | Resolved 2/2 referenced IDs. |
| IQR-MODEL-REPRODUCE | model | PASS | Independent deterministic recalculation matched. |
| IQR-AUDIT-TRAIL | ai_governance | PASS | Run ID: 5424942239904a88beac86dd8db8e93c. |
| IQR-REPORT-CONTRACT | report | PASS | Required headings complete. |
| IQR-REPORT-CONSISTENCY | report | PASS | Report values match structured output. |
| IQR-ACTION-COMPLETE | report | PASS | All triggered signals have accountable actions. |
| IQR-ASSURANCE-BOUNDARY | report | PASS | No prohibited assurance language detected. |

## 人工签署

状态：`pending`。自动质量控制通过不能替代项目负责人签署。

## 审计轨迹

- Run ID：`5424942239904a88beac86dd8db8e93c`
- Code version：`portfolio-demo`
- Input hash：`18b467d2c7d38325f727c22138aa1a3f10f06d02f80a96336074a612a4cee3cd`
- Output hash：`89a6bc5e959acc1a2c31e48b4d03d1dd3591c4b1160609f7a1fdc89282f08c60`

## 证据附录

- **DEMO-FR-E1｜示例智造2025年度结构化财务数据**（QuantResearchAgent synthetic fixture，2026-03-31）：收入、净利润、经营现金流、资产负债、应收、存货、毛利率和非经常性损益的合成演示口径。
- **DEMO-FR-E2｜示例智造2024年度结构化财务数据**（QuantResearchAgent synthetic fixture，2025-03-31）：用于同比基准的上一年度合成财务口径。

## 方法警示

- This scorecard identifies screening signals, not fraud or audit conclusions.
- Thresholds are transparent portfolio-demo rules and require sector calibration.
