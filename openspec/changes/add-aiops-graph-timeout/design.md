## Context

solution3.md 问题7：诊断图运行处无整体超时，LLM 卡住会长期占用后台任务槽位。方案要求整图 wall-clock 超时 + 降级报告 + `timed_out` 任务状态 + SSE `timeout` 事件。

## Goals / Non-Goals

**Goals:**

- 整图执行（含 LLM 与工具调用）施加 wall-clock 超时，超时后不再占用任务槽位
- 超时任务生成含已收集证据的降级报告，用户可查看部分结果
- SSE 事件序列与正常完成一致（report → task.status → complete）

**Non-Goals:**

- 不改变正常执行路径的行为与事件序列
- 不新增独立 SSE 事件类型，复用 `task.status` 并扩展 `timed_out` 状态值

## Decisions

- **超时机制**：`asyncio.wait_for(update_stream.__anext__(), timeout=remaining)` + deadline 递减，Python 3.10 兼容（`asyncio.timeout` 需 3.11+，项目目标 3.10）；每次迭代用剩余预算，整图累计不超时
- **超时中断**：取消 `__anext__` 传播到图内部当前步骤，随后 `aclose()` 清理 async generator
- **已收集证据**：超时后从 owner 作用域仓库 `list_evidence` 读取已持久化证据（executor 每步已写入 SQLite），不依赖被取消的图状态
- **降级报告**：新增 `_timeout_report_content`，保留"告警分析报告"必需标题结构，如实列出已收集证据
- **契约**：`TaskStatusSseEvent.status` 增加 `timed_out`（共享契约 + 后端 Literal 同步）
- **可配置**：`AiopsDiagnosticService(graph_timeout_seconds=600)`，测试注入小值

## Risks / Trade-offs

- [wait_for 取消传播] → 图内部进行中的 LLM/MCP 调用会被取消，符合"超时中断"语义；已完成的步骤证据已持久化
- [超时阈值过短误伤长诊断] → 默认 10 分钟，可通过构造参数调整

## Migration Plan

无 schema 变更。新增任务状态值 `timed_out` 为追加式，不影响既有查询与前端（前端只按类型透传）。
