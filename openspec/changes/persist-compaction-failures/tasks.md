## 1. 持久化

- [x] 1.1 Alembic 迁移 `202608210001`：chat_sessions 加 last_compaction_error / last_compaction_failed_at
- [x] 1.2 models / repositories / sqlite 三处同步

## 2. 记录与清除

- [x] 2.1 硬限压缩失败记录 error；成功压缩（archive）清除
- [x] 2.2 工具压缩降级在 _compression metadata 加 compressionFailed 标记

## 3. 契约与测试

- [x] 3.1 ChatMemoryState 契约加 lastCompactionError / lastCompactionFailedAt；前端 mock 同步
- [x] 3.2 测试：失败记录 error、成功压缩清除、前端 typecheck/test
- [x] 3.3 全量 ruff/pyright/pytest 通过；更新问题 3 记录与 WIKI
