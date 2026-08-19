## Why

切换到 manual 模式或显式手动压缩时，当前请求会串行压缩全部未压缩历史；长会话会因多次 LLM 调用长时间阻塞。手动操作应尽快返回，并让既有持久任务在后台按批次完成压缩。

## What Changes

- 将 manual 模式切换和显式压缩改为仅投递一次聊天记忆压缩任务
- 在两个聊天记忆接口响应中返回已投递的后台任务，供前端查询状态
- 保留后台任务每次仅压缩一个受预算限制批次的既有语义

## Capabilities

### New Capabilities

- `manual-chat-memory-compaction`: 手动记忆压缩的异步投递与任务状态返回

### Modified Capabilities

- `chat-memory-management`: manual 模式和显式压缩不再在请求内完成全量压缩
- `background-job-runtime`: 聊天记忆压缩任务作为可查询的手动操作结果返回

## Impact

- `apps/backend/src/super_ai/chat/memory.py`
- `apps/backend/src/super_ai/api/app.py`
- `packages/api-contracts/src/chat.ts` 与 `packages/api-contracts/src/openapi.ts`
- 聊天记忆测试、OpenSpec WIKI 与问题 4 记录
