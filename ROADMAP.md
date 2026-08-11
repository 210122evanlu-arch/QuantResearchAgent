# QuantResearchAgent MVP Roadmap

本路线图按照“每轮都能验证、每轮不引入过多变量”的原则推进。完成一轮并通过验收后，再进入下一轮。

## MVP Build Track

### Round 0：项目基线与开发环境（已完成）

任务：

- 建立 GitHub 项目骨架和 Python 虚拟环境。
- 定义 ResearchState、7 个阶段 Schema、枚举和通用子模型。
- 增加数据范围、显著性和评审路由校验。
- 建立最小 LangGraph 编译测试和 Schema 测试。
- 配置 `.env.example` 与 `.gitignore`。

验收标准：

- `pip check` 无依赖冲突。
- `pytest` 全部通过。
- `main.py` 可以编译 LangGraph。

### Round 1：Node 接口与 LLM 基础设施（已完成）

任务：

- 为 7 个 Node 定义统一输入、输出和错误处理约定。
- 增加环境变量加载、模型配置和 LLM 客户端工厂。
- 使用 Pydantic Structured Output，禁止 Node 返回自由格式字典。
- 支持依赖注入，使测试可以使用 Fake LLM，不消耗真实 API。
- 增加基础日志，并确保日志不会记录 API Key。

验收标准：

- 每个 Node 都能在 Fake LLM 下返回对应 Schema。
- 缺少配置时给出清楚错误，而不是在调用深处失败。
- 单元测试不需要网络和真实 API Key。

### Round 2：Research Manager 与 Research Analysis（已完成）

任务：

- 实现 Research Manager Node，生成 ResearchPlan。
- 实现 Research Analysis Node，生成 ResearchAnalysis。
- 设计文献引用输入接口和来源验证规则。
- 明确禁止生成无法核验的虚构论文。
- 支持根据文献与理论修订初始假设。

验收标准：

- 给定研究问题可以生成结构完整的 ResearchPlan。
- ResearchAnalysis 中的每篇文献都有可追溯来源或明确标记为待核验。
- refined_hypotheses 能与原 hypothesis_id 对应。

### Round 3：Model Design 与 Data Preparation（已完成）

任务：

- 实现 Model Design Node，输出可解释的公式、变量角色和估计方法。
- 实现 Data Preparation Node，输出 DataProfile。
- 建立金融数据适配器接口，先支持本地 CSV/Parquet 示例数据。
- 实现缺失率、重复率、样本区间和偏差检查。
- 校验模型变量是否都能在数据中找到。

验收标准：

- ModelDesign 可以映射为实验所需的因变量、自变量和控制变量。
- DataProfile 的质量指标由代码计算，而不是由 LLM 猜测。
- 缺失字段或日期穿越会阻止实验开始。

### Round 4：Experiment 与金融统计工具（已完成）

任务：

- 实现 Experiment Node。
- 在工具层实现 OLS、稳健标准误和基础显著性检验。
- 为首个案例实现 Fama-MacBeth 回归或组合排序中的一种。
- 输出 StatisticalResult、ModelMetrics 和 RobustnessCheck。
- 保存可复现的实验参数、数据版本和结果文件。

验收标准：

- 使用固定样例数据可以重复得到一致结果。
- coefficient、t-stat、p-value 和 significant 保持一致。
- 至少包含一个稳健性检验及其通过/失败结果。

### Round 5：Research Committee 与修改闭环（已完成）

任务：

- 实现 Reviewer 与 Risk Analyst 的委员会评审逻辑。
- 输出 ReviewResult、结构化 ReviewIssue 和唯一 revision_target。
- 将 7 节点工作流接入 `workflow.py`。
- 实现 Approved、Model Issue、Data Issue、Experiment Issue 条件路由。
- 实现 revision_count、max_revisions 和超限人工处理策略。

验收标准：

- 四条路由分支都有自动化测试。
- Graph 不会无限循环。
- Approved 只能进入报告节点，Need Revision 必须有修改目标和问题清单。

### Round 6：Report Generator 与端到端案例（已完成）

任务：

- 实现 Report Generator Node 和 FinalReport。
- 生成结构化 Markdown 研究报告。
- 报告覆盖背景、假设、方法、数据、结果、稳健性、风险和结论。
- 完成 IVOL 研究 Demo，从问题输入运行到报告输出。
- 在报告中保留模型、数据和评审的可追溯信息。

验收标准：

- 一条命令可以完成端到端 Demo。
- 最终报告中的数字与 ExperimentResult 一致。
- 未通过评审的结果不会被写成无保留的正式结论。

### Round 7：工程质量与 MVP 发布（已完成）

任务：

- 增加依赖锁定文件和 CI 测试。
- 增加覆盖率、类型检查、格式检查和错误日志。
- 完善 README、架构说明、配置说明和风险免责声明。
- 检查密钥、数据许可和报告输出是否会被误提交。
- 准备 GitHub 首次提交与 MVP 标签。

验收标准：

- 新环境可以根据文档完成安装和测试。
- CI 自动通过。
- 仓库中不包含 API Key、受限数据或生成的敏感报告。
- MVP Demo、测试和文档保持一致。

## Platform Expansion Track

### Platform Round 1：上市公司深度研究（已完成）

已完成：

- 建立公司研究专属 Schema、状态字段和输入校验。
- 将财务报表分析、战略诊断、相对估值和同业比较拆成独立分析方法。
- 接入 Debate Gate、研究委员会质量检查和修改次数保护。
- 支持注册到平台 WorkflowRegistry，并生成带证据索引的 Markdown 报告。
- 增加 BYD 离线样例，证明路由到报告的端到端闭环。

### Platform Round 2：公司公开数据自动采集（已完成）

- 接入上市公司法定披露元数据、PDF 链接、行情和财务指标采集器。
- 使用 BaoStock 自动获取免 Key 行情、估值倍数和按发布日期筛选的财务指标。
- 使用 CNInfo 自动解析证券标识并获取法定披露标题与 PDF 链接。
- 用代码计算收益率、波动率、最大回撤、同业中位数和估值溢折价。
- 增加截止日、证据引用和数据不足阻断测试。

### Platform Round 3：财报全文与专业研究报告（已完成）

- 下载、校验并缓存定期报告 PDF，提取业务模式、管理层讨论、业务分部、现金流和风险页面。
- 为每个年报页面生成稳定 Evidence ID，并校验 LLM 引用不存在悬空证据。
- 使用 DeepSeek 生成受页级证据约束的中文研究叙事。
- 输出 Partner 风格核心观点、盈利质量、二维风险矩阵、相对估值和行动路线。
- 生成专业 Word 报告，并使用 LibreOffice/Poppler 完成八页视觉验收。
- 保存完整 LangGraph 状态为结构化 JSON artifact，供报告渲染器重复使用。

### Platform Round 4：事件情报与 API 交付（已完成）

- 对公告和新闻元数据进行分类、重大性识别、证据去重和报告更新判断。
- 提供 FastAPI 输入层、任务状态、报告下载、运行指标和可注入执行器。
- 保留公告全文影响链分析与持久化任务队列作为后续生产化工作。

### Platform Round 5：估值与量化能力泛化（已完成）

- 增加通用实体固定效应、交易成本后 Backtest 和动量研究案例。
- 增加 DCF、WACC×永续增长敏感性分析和公司研究估值接口。
- 保留自动可比公司筛选、完整行业基准和持牌数据接入作为后续工作。

### Platform Round 6：评测、可观测性与发布验收（已完成）

- 为研究任务记录生命周期时间、执行耗时和结构化失败类别。
- 提供不暴露提示词、报告正文、密钥和本地路径的运行指标接口。
- 建立覆盖六条业务线与五份作品集报告的确定性评测基线。
- 将业务能力评测、测试覆盖率、类型检查、安全审计和依赖审计统一接入 CI。
- 补充故障分类、排查顺序、可信边界和发布验收文档。

### Platform Round 7：行业研究专属工作流（已完成）

- 建立 Industry Research Schema、分析合成、委员会评审和定向返工闭环。
- 组合行业结构、同业对照和情景分析三类独立分析引擎。
- 输出产业链、需求与竞争格局、情景矩阵、监测指标和证据附录。
- 增加高端白酒两家公司公开信息快照，并明确样本与报告期边界。
- 将行业研究接入 Research Jobs API、发布评测与作品集材料。

## Backlog

- 建设市场策略与统计事件研究的专属数据及执行工作流。
- 扩展行业研究的自动数据采集、统一报告期和完整可比公司覆盖。
- 将进程内任务状态升级为持久化队列、鉴权、分布式追踪与监控后端。
- 在持牌点时数据上扩展自动可比公司筛选、行业基准和多公司组合研究。
