## MODIFIED Requirements

### Requirement: Managed MCP runtime assembly
聊天与 AIOps SHALL 从当前用户启用的 MCP 连接装配工具；无用户记录时 SHALL 使用项目 CLS 默认连接。运行时 SHALL 在当前用户的启用连接配置未变化时复用客户端，并在配置改变后释放旧客户端资源。

#### Scenario: 连接被禁用
- **WHEN** 用户禁用连接
- **THEN** 后续 Agent 执行 MUST NOT 加载或调用该连接工具。

#### Scenario: 配置未变化时复用客户端
- **WHEN** 同一用户连续启动聊天或 AIOps 诊断且启用连接配置未变化
- **THEN** 系统 MUST 复用现有的受管理 MCP 客户端。
