## ADDED Requirements

### Requirement: Diagnostic execution timeout
后端 SHALL 对每个诊断的 Plan-Execute-Replan 图执行施加整图 wall-clock 超时。超时时 MUST 取消图执行并将任务标记为 `timed_out`，MUST 持久化包含已收集证据的降级 Markdown 报告，MUST 以 `task.status`（`timed_out`）、`report`、`complete` 的 SSE 事件序列结束流。

#### Scenario: Graph exceeds the wall-clock budget
- **WHEN** 图执行（含 LLM 与工具调用）超过配置的超时预算
- **THEN** 后端 MUST 取消图执行，将任务更新为 `timed_out`，生成并持久化含已收集证据的降级报告，并发送 `task.status`（`timed_out`）、`report`、`complete` SSE 事件。
