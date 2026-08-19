## Why

进程内聊天锁无法覆盖多 worker，导致同会话并发请求可交错写入。

## What Changes

- 使用 SQLite 条件更新获取和释放 owner/session 范围的执行租约。
- 租约冲突时聊天流返回明确繁忙错误。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `stream-rag-chat`: 同会话聊天执行在多进程间互斥
- `memory-repositories`: 聊天会话提供 owner 范围执行租约

## Impact

- 聊天会话模型、迁移、repository、SSE 错误合同和测试。
