## Why

摘要仅推进计数边界，原始消息一直留在聊天热表，导致每轮聊天反复读取全量历史，长会话的 SQLite 查询和内存占用持续增长。

## What Changes

- 将已被记忆摘要覆盖的聊天消息迁入 owner 范围的归档表，保留原文和元数据
- 让聊天运行时只读取活跃消息，避免把归档历史重新装入 Agent 上下文
- 保持会话历史读取能合并归档与活跃消息，清除或删除会话时同步处理归档记录

## Capabilities

### New Capabilities

- `archived-chat-history`: 已压缩聊天记录的可追溯归档和生命周期管理

### Modified Capabilities

- `chat-memory-management`: 压缩完成后将已覆盖历史从热上下文移出
- `memory-repositories`: 为归档消息与活跃消息提供 owner 范围仓库操作
- `chat-sessions`: 读取、清除和删除会话时涵盖归档消息

## Impact

- 聊天记忆服务、流式聊天服务和 SQLite Repository
- SQLAlchemy 模型与 Alembic 迁移
- 聊天记忆和 Repository 回归测试、OpenSpec WIKI 与问题 14 记录
