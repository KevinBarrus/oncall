## Why

`/metrics` 只有请求计数/失败数/平均延迟，缺少业务级指标，无法观测 chat 流量、上下文占用、压缩健康与 MCP 调用延迟。

## What Changes

- `observability.py` 新增业务指标 registry（`record_business_metric`：total + samples，端点按 total/count 给平均）
- 注入指标点：chat 流请求数、会话上下文 token（平均）、记忆压缩成功/失败、工具压缩降级、MCP 工具调用延迟
- `/metrics` 端点输出 `business` 段

## Capabilities

纯可观测性增强，不修改任何契约，`skip_specs: true`。

## Impact

- observability.py registry + reset（测试隔离）
- chat/memory/streaming/mcp_client 指标点
- /metrics 端点扩展 + 新测试
