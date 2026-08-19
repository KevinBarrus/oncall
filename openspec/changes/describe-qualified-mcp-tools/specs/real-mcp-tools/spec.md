## MODIFIED Requirements

### Requirement: Real MCP SSE tools

系统 SHALL 通过当前用户启用的受管理 MCP 连接接入真实 Server，并 SHALL 在用户未配置连接时回退到项目 CLS SSE 配置。多个 Server 的工具发生名称冲突时，系统 MUST 使用 provider 限定的 Agent 工具名，并在该工具 description 中说明 provider、原始 MCP 工具名和限定调用名。

#### Scenario: Agent loads managed tools
- **WHEN** 用户启动聊天或 AIOps 诊断
- **THEN** Agent MUST 只加载该用户启用连接中真实发现的工具。

#### Scenario: MCP tool names conflict
- **WHEN** 两个启用 MCP Server 返回相同的工具名称
- **THEN** Agent MUST 看到各工具的 provider、原始工具名和各自限定调用名，并能够通过限定名调用正确 Server。
