## Why

solution3 问题7 在共享契约为 `TaskStatusSseEvent.status` 增加 `timed_out`（后端 SSE 与降级报告已落地），但前端 `STATUS_DESCRIPTIONS` 映射表缺失该条目，超时诊断的历史记录显示"状态未知"（neutral）——三端同步在最后一环漏了 UI 标签映射。

## What Changes

- `asyncStatus.ts` 增加 `timed_out: { label: "诊断超时", tone: "danger", active: false }`
- 前端组件测试补充 timed_out 断言

## Capabilities

前端超时状态标签映射，`skip_specs: true`。

## Impact

- apps/frontend/src/ui/asyncStatus.ts
- apps/frontend/tests/chineseWorkspace.test.ts
