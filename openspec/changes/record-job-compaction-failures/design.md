## Context

solution4.md 问题9（P2）：后台 job 失败（`app.py:1796-1822`）不进会话记账；`chat/memory.py:165-178` 仅内联路径记账。

## Goals / Non-Goals

**Goals:**

- 后台压缩失败与会话 `lastCompactionError` 可见性对齐（两条路径一致）

**Non-Goals:**

- 不改 job 重试/退避语义（异常仍重新抛出交给 runtime）

## Decisions

- handler 的 `compact_once` 包 try/except：先 `update_memory_state(last_compaction_error=exc.__class__.__name__, last_compaction_failed_at=now)`，再 `raise` 交给 runtime（job failed + 退避重试）
- 测试：mock `_chat_memory_context` 返回抛错的 service，断言会话记录压缩错误

## Risks / Trade-offs

- [记账与 job 失败状态可能短暂不一致] → 记账先行、随后 job failed，最终一致（同一异常路径）

## Migration Plan

无。
