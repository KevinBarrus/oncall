## Why

聊天和诊断会在每次请求、每次工具调用时重新建立 MCP 会话，导致重复握手、额外延迟和连接资源浪费。随着工具调用次数增加，这会直接放大 AIOps 诊断的执行成本。

## What Changes

- 在应用运行期按用户启用连接配置复用 MCP 客户端，并在配置变化或应用关闭时释放会话
- 在 MCP 客户端内复用单个 Server 的已初始化会话，并缓存短时间内的工具发现结果
- 让 LangChain 暴露的 MCP 工具通过统一的 MCP 执行器调用，避免绕过复用会话

## Capabilities

### New Capabilities

- `mcp-session-reuse`: 定义 MCP 会话、工具发现缓存与生命周期管理

### Modified Capabilities

- `mcp-connection-management`: 受管理连接运行时复用用户当前配置对应的客户端
- `real-mcp-tools`: Agent 工具发现和调用复用受管理 MCP 会话

## Impact

- 影响 `mcp_client.py`、`mcp_connections.py`、`tool_registry.py` 和应用 lifespan
- 不改变 HTTP 或 SSE 对外契约，不新增依赖
