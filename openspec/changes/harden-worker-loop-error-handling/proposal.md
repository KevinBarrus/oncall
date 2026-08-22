## Why

`_worker_loop` 是裸 while 循环，`_claim_available` 与 `_execute` 的仓储调用（claim_next / mark_succeeded / mark_cancelled / handle_failure）抛出的瞬时异常（SQLite busy 超时、磁盘 I/O）会直接终止 worker task——后台处理（记忆压缩、文档索引、AIOps 诊断）静默停摆直到重启进程，无告警无事件。

## What Changes

- `_worker_loop` 每轮包 try/except：异常时 emit `background.worker.error` 事件 + 指数退避（2s→30s 封顶）后继续
- `_execute` 三个状态记账点（mark_succeeded / mark_cancelled / handle_failure）各自兜底：失败只 emit 事件，状态事件仅在持久化成功时发出

## Capabilities

worker 循环自愈语义，`skip_specs: true`。

## Impact

- jobs/runtime.py（worker_loop 防护 + 记账兜底 + `_worker_backoff`）
- tests/test_extended_capabilities.py（3 个存活回归测试）
