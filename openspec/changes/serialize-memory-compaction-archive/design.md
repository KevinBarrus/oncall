## Context

solution4.md 问题2（P1）：后台压缩 job handler 与 REST append 不持执行租约，与流内 95% 硬限内联压缩可并发；`archive_compacted_messages` 按前缀数量归档，交错时可能抛 RuntimeError 或归档未被摘要覆盖的消息；压缩入队无去重。

## Goals / Non-Goals

**Goals:**

- 归档操作只归档本次摘要实际覆盖的消息（CAS）
- 自动压缩不重复入队
- 交错发生时一方明确失败（可重试/可观测），而非静默归档错误消息

**Non-Goals:**

- 不给 REST append / job handler 加执行租约（改动面大；CAS + 去重已消除错误归档与无谓并发，剩余交错由失败-重试自愈）
- 不改流式路径（流式已持 15 分钟租约）

## Decisions

- **CAS 按 ID 集合**：`archive_compacted_messages(message_ids=...)` 事务内取 active 前 `len(message_ids)` 行，校验 ID 集合完全一致才归档。依据：消息 append-only（新消息只会到末尾），`_select_messages_for_compaction` 恒返回 uncompressed 前缀，因此"前缀 ID 集合 == 摘要覆盖集合"是正确归档的充要条件；不一致即证明期间发生归档交错 → 抛 RuntimeError 放弃（job 走重试，内联走 last_compaction_error 记账）
- **入队去重**：`_schedule_chat_memory_compaction` 默认 `dedupe=True`，`find_for_resource` 查到 queued/running 则返回 None；手动 `memory:compact` 端点传 `dedupe=False`（用户显式操作总是入队），mode 切换与 70% 自动触发走去重

## Risks / Trade-offs

- [CAS 失败导致压缩 job 重试直到窗口无交错] → job 有 max_attempts=3 与退避，LLM 摘要短暂交错后通常重试即成功；内联路径记录 last_compaction_error 可观测
- [去重误跳过手动触发] → 手动端点已豁免（dedupe=False）

## Migration Plan

无 schema 变更（repository 接口签名变化，仅内部调用方）。
