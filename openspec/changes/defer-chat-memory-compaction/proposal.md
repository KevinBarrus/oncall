## Why

聊天记忆达到自动压缩阈值时会在请求路径等待一次摘要模型调用；摘要调用或返回格式失败会直接中断本轮聊天。该行为延迟首个 SSE 输出，也让可恢复的摘要故障变成用户可见失败。

## What Changes

- 自动阈值触发的聊天记忆压缩改为投递既有持久后台任务，当前请求继续使用未压缩历史。
- 仅当候选上下文接近硬限时，才在请求内执行一次有超时的压缩以释放预算。
- 摘要超时、模型调用失败或格式无效时保留原记忆并记录可观测事件，不中断仍在预算内的聊天请求。

## Capabilities

### New Capabilities

- `deferred-chat-memory-compaction`: 定义聊天记忆的异步压缩、硬限同步兜底和失败降级语义

### Modified Capabilities

- `background-job-runtime`: 为聊天记忆压缩注册并执行既有持久任务
- `chat-memory-management`: 自动压缩的请求时机与失败语义变更

## Impact

- 影响 `apps/backend/src/super_ai/chat/memory.py`、聊天运行器与应用后台任务注册。
- 使用既有 SQLite job repository 和 BackgroundJobRuntime，不新增 API、依赖或数据库表。
- 补充聊天记忆和后台任务的回归测试。
