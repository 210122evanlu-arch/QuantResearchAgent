# QuantResearchAgent

**把一个模糊的研究课题或咨询委托，转化为有证据、有模型、有评审、可返工的专业报告。**

[![CI](https://github.com/210122evanlu-arch/QuantResearchAgent/actions/workflows/ci.yml/badge.svg)](https://github.com/210122evanlu-arch/QuantResearchAgent/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/210122evanlu-arch/QuantResearchAgent)](https://github.com/210122evanlu-arch/QuantResearchAgent/releases)
![Python](https://img.shields.io/badge/Python-3.11-3776AB)
![License](https://img.shields.io/badge/License-MIT-0f766e)

QuantResearchAgent 面向券商研究所、上市公司研究和管理咨询场景。它不是只负责“生成一段答案”的聊天机器人，而是一套将业务问题、公开披露、市场数据、金融模型、研究委员会和报告交付连接起来的多智能体工作流。

项目支持多模型 Provider，包括 **DeepSeek、Gemini 及 OpenAI 兼容接口**，并提供无需 API Key 的离线测试环境。统计计算、数据指纹、条件路由和审批状态由代码控制，模型主要负责结构化研究、证据解释与观点组织。

## 它能接什么业务委托？

| 服务线 | 客户问题示例 | 系统交付 |
| --- | --- | --- |
| 量化研究 | “投资者情绪是否预测未来收益？” | 研究计划、文献与理论、模型设计、回归/组合实验、稳健性结果、评审报告 |
| 上市公司研究 | “这家公司的增长质量、竞争力和估值如何？” | 财务质量、业务诊断、同业比较、相对估值、风险与证据附录 |
| 经营风险咨询 | “哪些风险应进入管理层未来 90 天议程？” | 风险优先级矩阵、关键争议、缓释措施、Owner、Timeline 与 KPI |
| 行业与市场策略 | “行业景气变化会影响哪些公司和指标？” | 驱动因素、情景假设、监测指标、影响路径与研究结论 |
| 事件研究 | “政策或公司事件带来了什么短中期影响？” | 事件窗口、对照基准、异常表现、机制解释与局限性 |

用户可以在输入层指定：**公司 / 证券代码、研究主题、截止日期、数据范围、是否需要辩论，以及期望的报告类型**。平台根据任务类型选择研究路线，最终仍汇总为统一、可复核的交付物。

## 从委托到交付

<p align="center">
  <img src="docs/assets/workflow-4x3.svg" width="880" alt="QuantResearchAgent 业务研究工作流" />
</p>

七个核心 Node 各自只读取 `ResearchState` 并返回结构化增量，Node 之间不直接调用。研究委员会决定通过或修改；需要修改时，Revision Router 会把任务送回模型、数据或实验节点，并通过修改次数上限防止无限循环。

公司研究和咨询任务共享同一套证据、分析、Debate Gate、委员会评审与报告能力。业务上的“质量控制”，在系统中被翻译为可执行规则：

| 业务要求 | 系统机制 |
| --- | --- |
| 观点必须有出处 | EvidenceRecord、页级证据 ID、文档哈希与截止日 |
| 数字不能由模型编造 | Data Preparation 与 Experiment 使用确定性代码执行 |
| 重大结论需要反方挑战 | Debate Gate 根据复杂度和风险决定是否进入辩论 |
| 报告不过审需要返工 | Decision Router + Revision Router 定向返回问题节点 |
| 项目不能无限讨论 | Moderator 与 `max_revisions` 控制辩论和修改次数 |
| 管理层需要行动方案 | 报告输出风险矩阵、Owner、Timeline、KPI 与证据附录 |

## 业务场景 Demo：上市公司风险咨询

**客户委托**

> 基于截止日内公开信息，评估比亚迪的经营、财务、治理与外部风险。识别管理层应优先处理的问题，并形成可以进入风险委员会议程的行动建议。

这个 Demo 会完成以下业务链路：

1. 将委托转化为公司、主题、截止日和交付目标；
2. 登记年度报告、产销公告、担保公告、关联交易和外部风险证据；
3. 建立风险清单并评估严重程度、影响、监测指标和缓释动作；
4. 由 Debate Gate 判断是否需要正反方讨论；
5. Moderator 区分“披露事实、合理推断和仍缺失的数据”；
6. 输出管理层风险优先级、委员会综合判断和咨询报告。

运行方式：

```powershell
.\.venv\Scripts\python.exe -m examples.business_risk_consulting_demo
```

示例终端摘要：

```text
Business scenario: listed-company risk consulting
Company: 比亚迪股份有限公司
Priority risks: 盈利质量与现金转化 / 销量与竞争压力 / 担保与集团信用暴露 / 地缘政治与海外合规
Deliverable: reports/advisory/byd_risk_advisory_demo.md
```

该场景使用固定的公开披露证据快照，在离线测试环境中即可跑通完整闭环。它演示的是业务流程、证据约束与报告结构，不构成对示例公司的实时判断或投资建议。

## 快速开始

### Windows PowerShell

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install pip==25.3
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.lock
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe main.py
```

### Linux / macOS

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install pip==25.3
.venv/bin/python -m pip install -r requirements-dev.lock
.venv/bin/python -m pytest -q
.venv/bin/python main.py
```

`main.py` 默认只编译 Graph，不访问网络，也不会产生模型调用。

## 更多可运行场景

以下 Demo 均可在离线测试环境中运行：

```powershell
# 7-Node 量化研究闭环：IVOL 研究设计、实验、评审与修改路由
.\.venv\Scripts\python.exe -m examples.ivol_research_demo

# 上市公司研究：财务质量、竞争地位、相对估值与同业比较
.\.venv\Scripts\python.exe -m examples.company_research_demo

# 六类研究与咨询服务线的输入路由
.\.venv\Scripts\python.exe -m examples.platform_routing_demo

# 独立的 Debate Gate 与多轮观点审查
.\.venv\Scripts\python.exe -m examples.debate_workflow_demo
```

量化示例报告见 [reports/example_report.md](reports/example_report.md)。

## 多模型 Provider

复制本地配置模板：

```powershell
Copy-Item .env.example .env
```

选择一个 Provider，并只在本地填写密钥：

```dotenv
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=your-api-key
DEEPSEEK_MODEL=your-model-name
```

Provider 层支持：

- DeepSeek；
- Gemini；
- OpenAI 兼容接口；
- 用于 CI、开发和演示的离线测试环境。

连接检查：

```powershell
.\.venv\Scripts\python.exe -m examples.llm_connection_demo
```

只有显式加入 `--live` 才会调用已配置的模型。生产组装层会将同一 Provider 注入需要语言推理的节点；数据准备、统计实验、Router 和数值报告仍保持确定性。

## 数据与证据能力

- **BaoStock**：无需 API Key 的 A 股行情、估值与部分财务数据；
- **CNInfo**：上市公司法定披露检索与年度报告 PDF；
- **Crossref**：论文元数据与期刊白名单检索；
- **Tushare Pro**：可选适配器，不是默认依赖；
- **CSV / Parquet**：支持本地研究面板和持牌数据的合规接入；
- **PDF Evidence Pipeline**：文件类型、大小、SHA-256、逐页文本与稳定证据 ID。

真实公开数据 Demo：

```powershell
# 免费行情数据，不调用模型
.\.venv\Scripts\python.exe -m examples.baostock_ivol_data_demo `
  --codes sz.000001,sh.600000,sz.000858,sh.600519 `
  --start 2023-01-01 `
  --end 2025-12-31

# 公司公告、年报 PDF 与已配置模型
.\.venv\Scripts\python.exe -m examples.company_research_filing_demo `
  --as-of-date 2026-08-08
```

运行时报告、下载 PDF、API 配置、持牌数据和市场缓存均被 Git 忽略。

## 技术结构

```text
QuantResearchAgent/
├── agents/             # Agent 角色与 Node 实现
├── analysis_engines/   # 财务、战略、估值与同业分析引擎
├── data_sources/       # 披露、行情、论文与本地数据适配器
├── graph/              # LangGraph、Router、Debate 与平台调度
├── literature/         # 期刊白名单与 Crossref 检索
├── llm/                # Structured LLM 与多 Provider 工厂
├── schemas/            # Pydantic Schema 与 ResearchState
├── tools/              # 统计、实验、评审与报告工具
├── examples/           # 业务、研究和数据 Demo
├── tests/              # 自动化测试
├── docs/               # 架构、数据和可信边界
└── reports/            # 运行时报告与批准发布的示例
```

核心设计文档：

- [平台架构](docs/platform_architecture.md)
- [Node 与 Schema 映射](docs/node_schema_mapping.md)
- [Debate Gate](docs/debate_gate.md)
- [研究委员会](docs/research_committee.md)
- [报告与证据规则](docs/reporting.md)
- [实验引擎](docs/experiment_engine.md)

## 可信边界

- 本项目是研究与咨询工作流原型，不是自动交易系统、持牌投顾系统、审计工具或监管合规意见；
- LLM 负责组织与解释已提供证据，统计数字、数据指纹、截止日、路由和审批状态由代码校验；
- `verified` finding 必须引用已登记的 EvidenceRecord，解释性判断明确标记为 `inferred`；
- 免费数据不能自动消除幸存者偏差、行业口径差异、复权误差或持牌数据缺口；
- 相对估值不等于目标价，最终结论需要具备资质的研究人员复核。

## 工程质量

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy agents data_sources graph literature llm schemas tools examples production.py config.py logging_config.py main.py
.\.venv\Scripts\python.exe -m pytest --cov --cov-report=term-missing
.\.venv\Scripts\python.exe scripts\release_audit.py
.\.venv\Scripts\python.exe -m pip_audit -r requirements.lock
```

GitHub Actions 在 push 与 pull request 时执行同一套质量门。发布审计会阻止 `.env`、疑似密钥、未批准二进制数据和运行时报告进入发布候选文件。

## 发布与贡献

- 当前版本：[v0.1.0](https://github.com/210122evanlu-arch/QuantResearchAgent/releases/tag/v0.1.0)
- 开发路线：[ROADMAP.md](ROADMAP.md)
- 更新记录：[CHANGELOG.md](CHANGELOG.md)
- 贡献约定：[CONTRIBUTING.md](CONTRIBUTING.md)
- 安全边界：[SECURITY.md](SECURITY.md)
- License：[MIT](LICENSE)
