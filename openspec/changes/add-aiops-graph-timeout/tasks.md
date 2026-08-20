## 1. 超时机制

- [x] 1.1 `AiopsDiagnosticService` 增加 `graph_timeout_seconds`（默认 600）
- [x] 1.2 图执行改为 deadline + `wait_for(__anext__)` 循环（3.10 兼容），超时取消并 `aclose()`

## 2. 超时降级路径

- [x] 2.1 `_handle_graph_timeout`：读已收集证据、生成 `_timeout_report_content` 降级报告、持久化 `timed_out` 任务与报告
- [x] 2.2 SSE 事件：`report` → `task.status`（`timed_out`）→ `complete`

## 3. 契约与测试

- [x] 3.1 共享契约 `TaskStatusSseEvent.status` 与后端 Literal 增加 `timed_out`
- [x] 3.2 超时测试：慢 Planner 桩 + 短超时，断言任务 `timed_out`、降级报告含已收集证据、SSE 事件序列
- [x] 3.3 更新主规格与问题 7 记录
