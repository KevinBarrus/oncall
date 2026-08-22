## Why

70% 触发的后台压缩 job 失败只进 job 表 `error_message` 并退避重试，不写 `last_compaction_error`——自动压缩连续失败时用户从会话 memory API 看不到失败原因，与 95% 内联路径的失败记账不对称。

## What Changes

- `_chat_memory_compaction_job_handler` 捕获 `compact_once` 异常，先写 `last_compaction_error`/`last_compaction_failed_at` 再重新抛出（job 走既有 failed/retry 语义）
- 回归测试：job handler 抛错后会话状态记录了压缩错误

## Capabilities

后台压缩失败会话可见性，`skip_specs: true`。

## Impact

- api/app.py（job handler 异常记账）
- tests/test_chat_sessions_api.py（1 个回归测试）
