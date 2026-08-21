## Context

solution3.md 问题3：压缩失败事件只写日志（`chat.memory.compaction_failed` / `chat.tool_compression.fallback`），未持久化到可查询表。方案：session 级 `last_compaction_error` / `last_compaction_failed_at` + memory API 返回；工具压缩失败在审计标记。

## Goals / Non-Goals

**Goals:**

- 用户可查询"上次自动压缩为何失败"
- 工具压缩降级在审计中显式标记

**Non-Goals:**

- 不新增独立失败事件表（session 字段足够，避免过度设计）
- 不改变压缩行为与降级语义

## Decisions

- `chat_sessions` 加 `last_compaction_error`（String 200）/ `last_compaction_failed_at`（DateTime），Alembic 迁移 `202608210001`
- `update_memory_state` 支持写入两个字段与 `clear_compaction_error`；`archive_compacted_messages` 成功路径清除
- `memory_payload` 输出 `lastCompactionError` / `lastCompactionFailedAt`（契约 `ChatMemoryState` 同步）
- 工具压缩降级：`_wrap_tool_output_compression` 的 `sampled_fallback` 模式在 `_compression` metadata 加 `compressionFailed: true`，随审计 result_summary 持久化

## Risks / Trade-offs

- [失败记录本身写入失败] → 与压缩失败同路径，罕见；不额外兜底
- [error 仅存类名] → 与既有事件一致，避免存敏感 message

## Migration Plan

Alembic revision `202608210001`，可回滚（drop_column）。
