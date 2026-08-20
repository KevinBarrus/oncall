## Why

AIOps 诊断的 Plan-Execute-Replan 图执行没有整图 wall-clock 超时：Planner/工具调用一旦卡住（模型 overload、网络抖动），会长期占用后台任务槽位，用户看到"执行中"无法判断是否卡死。

## What Changes

- 对整图执行施加可配置 wall-clock 超时（默认 10 分钟）
- 超时时：取消图执行、任务标记 `timed_out`、持久化含已收集证据的降级 Markdown 报告
- SSE 以 `task.status`（`timed_out`）+ `report` + `complete` 事件结束流
- 共享契约 `TaskStatusSseEvent.status` 增加 `timed_out` 状态值

## Capabilities

新增诊断执行超时保护（用户可见行为 + SSE 契约状态值扩展）。
