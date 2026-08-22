## Why

`compacted_message_count` 在归档表方案落地后恒为 0（archive/clear 均置 0），但 ORM/契约/切片算式仍保留，误导后续维护者（并为并发归档算式埋坑）。前端未使用该字段。

## What Changes

- Alembic 迁移 `202608210003` drop column `chat_sessions.compacted_message_count`
- 删除 ORM/record/update_memory_state 参数、clear/archive 置 0、`memory_payload` 的 `compactedMessageCount`
- `memory.py` 三处 `history[compacted_message_count:]` 切片改为直接使用 history（归档后 active 即未压缩消息）
- 契约 `chat.ts`/`openapi.ts` 删除 `compactedMessageCount`；前端测试 3 处、后端测试 6 处同步清理

## Capabilities

死字段清理，`skip_specs: true`。

## Impact

- alembic/versions/202608210003（drop column，可回滚）
- models.py / repositories.py / sqlite.py / chat/memory.py
- packages/api-contracts（chat.ts / openapi.ts）
- 前后端测试清理
