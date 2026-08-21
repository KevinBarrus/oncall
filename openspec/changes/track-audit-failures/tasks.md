## 1. 持久化

- [x] 1.1 Alembic 迁移 `202608210002`：chat_sessions 加 audit_failure_count（默认 0）
- [x] 1.2 models / repositories / sqlite 三处同步

## 2. 计数与 API

- [x] 2.1 审计失败时递增计数（owner 作用域），内层保护不破坏聊天流
- [x] 2.2 session payload 与 ChatSessionSummary 契约输出 auditFailureCount

## 3. 测试与记录

- [x] 3.1 测试：审计持久化失败递增计数
- [x] 3.2 前端 mock 同步；全量 ruff/pyright/pytest/契约/前端通过
- [x] 3.3 更新问题 4 记录与 WIKI
