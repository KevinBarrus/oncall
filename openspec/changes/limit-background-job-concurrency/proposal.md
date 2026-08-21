## Why

后台任务（文档索引、AIOps 诊断、记忆压缩）共享 worker 槽位，单一 kind 可能占满所有并发槽位：批量文档索引会阻塞记忆压缩，多个写密集任务同时执行触发 `SQLITE_BUSY`。

## What Changes

- `BackgroundJobRuntime` 增加 `max_concurrent_per_kind` 配置与执行中计数，`claim_next` 支持按 kind 过滤
- 领取时以 `asyncio.Lock` 串行化"检查槽位 → 领取 → 计数"，避免多 worker 竞态
- app.py 配置：`document_index`/`aiops_diagnosis`/`chat_memory_compaction` 各限 1

## Capabilities

纯内部后台任务限流，不修改任何产品能力或 API 契约，`skip_specs: true`。

## Impact

- jobs/runtime.py、memory/repositories.py（接口）、extended_sqlite.py（实现）
- app.py 后台运行时配置
- 新增 per-kind 并发限流测试
