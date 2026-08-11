# Node–Schema Mapping

## 主流程

| LangGraph Node | 对应 Agent | 读取 ResearchState | 生成并写入 |
| --- | --- | --- | --- |
| Research Manager | Research Manager Agent | `research_question` | `research_plan: ResearchPlan` |
| Research Analysis | Literature + Theory Agent | `research_plan` | `research_analysis: ResearchAnalysis` |
| Model Design | Quant Model Agent | `research_analysis` | `model_design: ModelDesign` |
| Data Preparation | Data Agent | `research_plan` + `model_design` | `data_profile: DataProfile` |
| Experiment | Experiment Agent | `model_design` + `data_profile` | `experiment_result: ExperimentResult` |
| Review | Reviewer + Risk Agent | `model_design` + `data_profile` + `experiment_result` | `review_result: ReviewResult` |
| Report | Research Assistant Agent | 全部已验证阶段结果 | `final_report: FinalReport` |

Experiment Node 内部按照 `model_design.estimator` 分发统计工具。详细设计参见 [`experiment_engine.md`](experiment_engine.md)。该 Router 属于实验引擎内部方法路由，不增加顶层 LangGraph Node 数量。

Review Node 由确定性 Risk Policy 与证据受约束的 Reviewer 共同组成，最终 decision 和唯一 revision target 由代码计算。详细设计参见 [`research_committee.md`](research_committee.md)。

Report Node 不调用 LLM；它从全部已验证阶段结果构建 FinalReport，并使用确定性模板生成 Markdown。详细设计参见 [`reporting.md`](reporting.md)。

## 为什么有两个加强输入

- Data Preparation 保留 `research_plan`，便于后续核对研究计划中的数据需求与模型变量；Round 3 的机器校验以 `model_design` 中的变量定义为准。
- Review 保留 `data_profile`，因为缺失率、重复率、前视偏差与生存者偏差属于评审和模型风险证据，不能只看实验结果。

## 调度原则

Node 只读取共享状态并返回增量 `dict`，不直接调用下一个 Node。固定边和修改循环全部由 LangGraph 负责。
