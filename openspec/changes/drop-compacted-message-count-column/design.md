## Context

solution4.md 问题11（P2）：`compacted_message_count` 死字段——archive/clear 置 0 后恒 0，契约暴露恒 0、前端未用，切片与算式误导维护者。

## Goals / Non-Goals

**Goals:**

- 删除字段（ORM/契约/算式全链路）
- 保留历史迁移不变（新迁移回滚兼容）

**Non-Goals:**

- 不改归档语义（active 历史即未压缩消息，无需边界字段）
- 不改 `context_tokens` 等其他记忆状态字段

## Decisions

- 新增迁移 `202608210003` drop column（downgrade 用 server_default="0" 补回，与创建迁移一致）
- `memory.py` 切片 `history[compacted_message_count:]` → `history`（归档后 active 即未压缩消息，切片恒为 no-op）
- 契约 `ChatMemoryState.compactedMessageCount` 删除（openapi.ts 同步 required/properties）
- 测试清理：后端 6 处断言、前端 3 处 fixture 字段

## Risks / Trade-offs

- [旧数据库升级] → drop column 幂等（列存在才删），downgrade 恢复带默认值
- [契约破坏] → 无外部消费者（单用户本地架构），前端已确认未使用该字段

## Migration Plan

迁移链升级 head + 回滚测试（test_memory_migrations 全链回滚覆盖新迁移）。
