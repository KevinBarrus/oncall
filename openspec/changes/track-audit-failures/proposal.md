## Why

工具调用审计持久化失败时只 emit `chat.tool_audit.failed` 日志事件、聊天继续，事后无法知道哪些会话丢失了审计。

## What Changes

- `chat_sessions` 增加 `audit_failure_count`（Alembic 迁移 `202608210002`）
- 审计持久化失败时递增计数（owner 作用域），失败不阻断聊天流
- session payload（`ChatSessionSummary`）新增 `auditFailureCount` 字段

## Capabilities

审计失败可观测性增强，新增 API 字段为追加式，`skip_specs: true`。

## Impact

- Alembic 迁移 + models/repositories/sqlite
- chat/streaming.py 审计失败计数
- 共享契约 chat.ts 字段 + 前端 mock
- 新增审计失败递增计数测试
