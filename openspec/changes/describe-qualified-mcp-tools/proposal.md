## Why

不同 MCP Server 暴露同名工具时，系统会为执行安全生成限定名，但没有把限定名及其来源告诉模型。模型无法可靠地区分应选择哪个 Server 的工具。

## What Changes

- 为发生名称冲突的 MCP 工具 description 补充 provider、原始工具名和限定 Agent 工具名
- 保持现有限定命名和按 provider 执行路由不变
- 补充同名 MCP 工具的 Agent 可见描述回归测试

## Capabilities

### New Capabilities

- 无

### Modified Capabilities

- `real-mcp-tools`: 同名 MCP 工具向 Agent 明确暴露来源和限定调用名

## Impact

- 影响 `tool_registry.py`、其单元测试、问题追踪和 OpenSpec WIKI
- 不改变 HTTP、SSE、MCP 管理 API 或依赖
