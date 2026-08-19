## Context

当前 `_SESSION_LOCKS` 仅存在于单个 Python 进程。

## Decisions

在 `chat_sessions` 存储 lease token 与过期时间。SQLite `UPDATE ... WHERE` 以 owner、session 和过期条件原子获取；流结束的 `finally` 按 token 释放。租约为 15 分钟，进程崩溃后可恢复。

## Risks / Trade-offs

- [异常长 Agent 执行超过租约] → 15 分钟后可恢复；需要更长运行时再增加续租
