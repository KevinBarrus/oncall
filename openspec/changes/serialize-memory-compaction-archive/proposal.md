## Why

记忆压缩有两条并发路径（后台 70% job 与流内/REST 95% 内联压缩）都在执行租约之外：旧实现按"当前 active 表前缀取 limit(message_count) 行"归档，交错时可能抛 RuntimeError 使一方压缩失败，极端交错下会归档未被摘要覆盖的新消息并用旧摘要覆盖新摘要；且 70% 后每条新消息都会重复入队压缩 job。

## What Changes

- `archive_compacted_messages` 改为**按消息 ID 集合 CAS 归档**：仅当 active 前缀 ID 集合与本次摘要覆盖集合完全一致（期间无更早消息被归档）时才归档，否则抛 RuntimeError 放弃
- `_schedule_chat_memory_compaction` 入队去重：同会话已有 queued/running job 时跳过（手动 `memory:compact` 端点 `dedupe=False` 总是入队）

## Capabilities

压缩归档 CAS 语义与自动入队去重，`skip_specs: true`。

## Impact

- memory/repositories.py + sqlite.py（接口 message_count → message_ids，CAS 校验）
- chat/memory.py（调用方传 ID 集合）
- api/app.py（入队去重 + 手动端点 dedupe=False）
- tests（CAS 拒绝陈旧集 + 入队去重 2 个回归测试）
