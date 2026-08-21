## Why

记忆压缩失败只发结构化日志事件，用户无法从 API 得知"上次自动压缩为何失败"，也无法统计哪些工具输出经常压缩失败。

## What Changes

- `chat_sessions` 增加 `last_compaction_error` / `last_compaction_failed_at`（Alembic 迁移）
- 压缩失败时更新字段；成功压缩后清除
- session memory payload（`ChatMemoryState`）新增 `lastCompactionError` / `lastCompactionFailedAt` 字段
- 工具输出压缩降级时在 `_compression` metadata 增加 `compressionFailed` 标记（随审计 result_summary 持久化）

## Capabilities

压缩失败可观测性增强，新增 API 字段为追加式，`skip_specs: true`。

## Impact

- Alembic 迁移 + models/repositories/sqlite
- chat/memory.py 失败记录与成功清除
- 共享契约 chat.ts 字段
- 新增压缩失败记录/成功清除测试
