## Why

非流式 REST append 端点（`POST /chat/sessions/{id}/messages`）的 user 分支执行 `prepare_message`（含 95% 内联压缩），但不获取执行租约，与流式端点不对称——流式执行中可并发触发压缩，与问题2 的压缩并发路径叠加。

## What Changes

- REST append user 分支获取/释放执行租约（`acquire_execution_lease` / `release_execution_lease`，与流式同 token 语义），流式执行中 append 返回 `CHAT_SESSION_BUSY`（409）
- 回归测试：持租约时 REST append user 消息返回 CHAT_SESSION_BUSY

## Capabilities

REST append 与流式执行互斥，`skip_specs: true`。

## Impact

- api/app.py（append user 分支包租约）
- tests/test_chat_sessions_api.py（1 个回归测试）
