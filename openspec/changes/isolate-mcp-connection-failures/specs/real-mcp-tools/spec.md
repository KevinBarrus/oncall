## MODIFIED Requirements

### Requirement: Real MCP SSE tools

系统 SHALL 通过当前用户启用的受管理 MCP 连接接入真实 Server，并 SHALL 在用户未配置连接时回退到项目 CLS SSE 配置。Agent MUST 只加载成功发现的真实工具；一个连接发现失败 MUST NOT 阻断其他健康连接的工具装配。

#### Scenario: Agent loads managed tools
- **WHEN** 用户启动聊天或 AIOps 诊断
- **THEN** Agent MUST 只加载该用户启用且成功发现的连接中真实工具。

#### Scenario: Agent calls a tool on an unavailable Server
- **WHEN** Agent 调用所属 MCP Server 在配置重试后不可用的已发现工具
- **THEN** 调用 MUST 返回该 Server 的明确失败，且不得影响其他 Server 已注册工具。
