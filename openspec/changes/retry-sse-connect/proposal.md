## Why

网络抖动、代理超时会导致 SSE 连接在建立阶段失败，前端直接抛错，用户需要手动重试；流中断错误也缺少清晰语义。

## What Changes

- `sseClient` 连接建立阶段（fetch + 2xx 检查）有限重试 2 次（500ms/1s 退避）
- 非 2xx 服务端错误不重试；流已开始后的中断不自动重发（避免 POST 流重复执行 Agent）

## Capabilities

纯前端传输层改进，不修改任何契约，`skip_specs: true`。

## Impact

- apps/frontend/src/api/sseClient.ts
- 新增 3 个重试行为测试
