## MODIFIED Requirements

### Requirement: Plan-Execute-Replan diagnostic graph
后端 SHALL 通过具有命名 `Planner`、`Executor`、`Replanner` 和 `Report` 节点的 LangGraph 工作流执行每个经过身份验证的 AIOps 诊断。Replanner 决策 SHALL 基于确定性规则（计划耗尽、连续失败次数、证据有无），MUST NOT 依赖 LLM 重新规划计划。

#### Scenario: Diagnostic follows the graph lifecycle
- **WHEN** 已认证的 user 启动诊断任务  
- **THEN** 后端 MUST 将任务保存为运行中，并在终端成功或失败前执行 Planner、Executor、Replanner 和 Report 节点。

#### Scenario: Replanner continues only when warranted
- **WHEN** Executor 返回需要其他限定诊断步骤的证据
- **THEN** Replanner MUST 依据确定性规则决定继续执行、回退到知识库检索或进入报告，并路由到 Executor 或 Report 节点。

#### Scenario: Replanner decisions are rule-driven
- **WHEN** Replanner 评估执行状态
- **THEN** 后端 MUST 依据规则决定交互契约（继续 / 规则触发的知识库回退 / 报告），MUST NOT 调用 LLM 重新规划计划。
