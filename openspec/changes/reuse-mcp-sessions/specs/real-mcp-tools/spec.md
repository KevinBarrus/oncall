## MODIFIED Requirements

### Requirement: Real MCP SSE tools
系统 SHALL 通过当前用户启用的受管理 MCP 连接接入真实 Server，并 SHALL 在用户未配置连接时回退到项目 CLS SSE 配置。Agent 的工具发现和调用 MUST 经由同一受管理运行时，以复用有效的 MCP 会话。

#### Scenario: Agent loads managed tools
- **WHEN** 用户启动聊天或 AIOps 诊断
- **THEN** Agent MUST 只加载该用户启用连接中真实发现的工具。

#### Scenario: Agent calls a discovered tool
- **WHEN** Agent 调用已发现的 MCP 工具
- **THEN** 调用 MUST 通过该工具所属 Server 的受管理 MCP 会话执行。
