## Context

solution3.md 问题4：审计失败只发日志事件。方案：assistant 消息 metadata 写 `auditFailed` 标记，或会话级累积 `audit_failure_count` 并在会话 API 返回。

## Goals / Non-Goals

**Goals:**

- 会话可查询"是否发生过审计失败、共几次"
- 审计失败不阻断聊天流（保持既有语义）

**Non-Goals:**

- 不新增独立审计失败事件表（会话计数足够，避免过度设计）
- 不定位具体哪次调用失败（日志事件已含 toolName）

## Decisions

- 采用方案第二条路径：会话级 `audit_failure_count`（迁移 `202608210002`，默认 0）
- repository 新增 `increment_audit_failure_count`（owner 作用域）；`_persist_tool_call_audit` 的 except 块内调用，且用内层 try/except 保护——审计记账失败也不得破坏聊天流
- `_chat_session_payload` 输出 `auditFailureCount`，契约 `ChatSessionSummary` 同步，前端 mock 更新

## Risks / Trade-offs

- [计数只增不减] → 符合"失败次数累积"语义；不提供清零（重置属产品决策）
- [increment 与 audit 同库失败] → 内层 try/except 保证不破坏聊天流

## Migration Plan

Alembic revision `202608210002`，可回滚（drop_column）。
