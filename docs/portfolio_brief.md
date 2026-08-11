# QuantResearchAgent｜项目速览

## 一句话定位

面向证券研究与管理咨询的可追溯多智能体研究平台：将研究规划、公开证据、金融模型、确定性计算、委员会评审和专业报告纳入同一条可返工工作流。

## 解决什么问题

金融研究 Agent 的难点并不是生成一段看似专业的文字，而是确保研究问题被正确拆解、数据和文献可以追溯、数值可以复现、重大判断经过挑战，并在证据不足时保留可信边界。本项目将这些要求编码为 Schema、Router、统计执行器、Debate Gate、Research Committee 和报告质量门。

## 已验证的业务交付

| 服务线 | 代表案例 | 可验证产物 |
| --- | --- | --- |
| 经营风险咨询 | [比亚迪公开信息风险咨询](../reports/showcase/byd_risk_advisory.md) | Partner View、二维风险矩阵、90 天行动路线、Owner/Timeline/KPI、证据附录 |
| 上市公司研究 | [贵州茅台公司深度研究](../reports/showcase/moutai_company_research.md) | 财务质量、竞争位置、同业比较、估值框架、委员会意见 |
| 行业研究 | [高端白酒行业研究](../reports/showcase/baijiu_industry_research.md) | 产业链、龙头经营分化、三情景矩阵、监测指标与证据边界 |
| 量化研究 | [动量因子研究](../reports/showcase/momentum_factor_research.md) | 固定效应回归、交易成本后回测、风险收益指标与研究边界 |
| 估值分析 | [DCF 敏感性分析](../reports/showcase/dcf_sensitivity_showcase.md) | 显式现金流假设、企业价值、股权价值、WACC×永续增长矩阵 |
| 事件情报 | [公告与新闻更新提示](../reports/showcase/event_intelligence_showcase.md) | 去重、重大性判断、观察清单与报告更新决策 |

市场策略和统计事件研究已经具备输入、路由和模板契约，但尚未包装成端到端交付。具体成熟度见[能力状态表](capability_status.md)。

## 技术与研究设计亮点

- 七节点 LangGraph 将规划、分析、模型、数据、实验、评审和报告解耦，Node 只读写 `ResearchState`。
- Decision Router 与 Revision Router 支持模型、数据和实验问题的定向返工，并通过修订次数限制保证流程终止。
- LLM 负责结构化研究推理；数据画像、回归、回测、估值、显著性、指纹和审批状态由代码计算。
- 文献、公告和财报通过 Evidence ID、来源、时间戳、页码和哈希建立引用链。
- Debate Gate 只在高风险、低置信度、证据冲突或用户要求时进入对抗审查，Moderator 决定何时结束。
- FastAPI 提供任务提交、状态、报告下载、事件分析和脱敏运行指标；执行器可替换为真实工作流或外部队列。

## 工程证据

- Python 3.11，Pydantic Structured Output，LangGraph，pandas/statsmodels，FastAPI。
- DeepSeek、Gemini 和 OpenAI 兼容 Provider；离线环境不需要 API Key。
- 252 项自动化测试，总覆盖率 85.94%，六条服务线与六份报告的 12/12 发布评测。
- Ruff、mypy、pytest、依赖漏洞审计、密钥/数据发布审计和文档一致性审计统一进入 GitHub Actions。

## 面试中的 60 秒介绍

> 我设计的不是一个直接回答金融问题的聊天机器人，而是一套研究生产流程。用户提交量化课题、公司研究、行业研究或风险咨询委托后，系统先结构化研究目标和证据范围，再由模型设计、数据准备和确定性分析引擎完成研究。结论必须经过 Research Committee；发现模型、数据或实验问题时，LangGraph 会定向返回相应节点修改。项目还加入 Debate Gate、证据 ID、截止日控制、回测和估值引擎、专业报告模板，以及 API、评测和运行诊断。目前已经用 IVOL、动量、贵州茅台、白酒行业和比亚迪等不同案例验证平台并不依赖单一研究主题。

## 可信边界

这是研究工程与咨询交付平台，不是自动交易系统、持牌投资顾问、审计工具或合规意见。公开和免费数据不能自动消除幸存者偏差、点时口径差异及数据许可限制；正式研究仍需具备资质的研究人员复核。
