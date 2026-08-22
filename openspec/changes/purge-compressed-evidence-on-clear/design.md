## Context

solution4.md 问题8（P2）：`clear_messages`（sqlite.py:276-326）不清理 `compressed_tool_evidence` 与审计行；`delete_session` 无此问题（FK CASCADE）。evidence 写入无去重，每次压缩调用新增一行原文。

## Goals / Non-Goals

**Goals:**

- 清空会话消息时同步清理证据原文与审计
- 同一 (会话, source_hash) 不重复写入原文（去重）

**Non-Goals:**

- 不引入 evidence 大小上限（原文可展开是设计语义；去重已消除重复膨胀）
- 不改 `delete_session`（级联已正确）

## Decisions

- `clear_messages` 在同一事务内追加两条 delete（`CompressedToolEvidenceModel` 按 chat_session_id、`AgentToolCallAuditModel` 按 chat_session_id——audit 的 diagnostic 关联行不受影响）
- `create` 先查 `(owner, chat_session_id, source_hash)` 已有行，命中直接返回（不重复写原文）；事务内查询+写入保持原子
- 测试：同 hash 两次 create 返回同一 id；clear 后 evidence.get 为 None、audit 列表为空

## Risks / Trade-offs

- [create 查询开销] → 每次压缩多一次等值查询，SQLite 索引覆盖（source_hash 已有列），可接受

## Migration Plan

无 schema 变更。
