## Why

用户启用多个 MCP 连接时，任意一个 Server 的工具发现失败会阻断全部聊天和诊断工具装配。健康连接因此不可用，降低了系统在部分外部依赖故障时的可用性。

## What Changes

- 工具发现按 MCP 连接隔离失败，继续注册健康连接返回的真实工具
- 在 MCP readiness 中返回逐连接的安全状态、工具数量与不可用原因
- 保持工具调用按所属连接失败，不伪造工具或诊断证据

## Capabilities

### New Capabilities

- `mcp-connection-isolation`: 定义多 MCP 连接发现与 readiness 的故障隔离行为

### Modified Capabilities

- `real-mcp-tools`: 多连接场景下仅加载健康连接的真实工具

## Impact

- 影响 `mcp_client.py`、MCP 相关测试、问题追踪和 OpenSpec WIKI
- 不改变 MCP 管理 API、聊天 SSE 或新增依赖
