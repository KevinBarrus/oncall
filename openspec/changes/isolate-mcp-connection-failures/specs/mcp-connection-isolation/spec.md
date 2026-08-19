## Purpose

定义多 MCP 连接并存时的工具发现和 readiness 故障隔离，确保一个外部 Server 失效不阻断其他真实工具。

## ADDED Requirements

### Requirement: MCP discovery isolates failed connections

系统 SHALL 分别发现每个启用 MCP 连接的工具。单个连接在配置重试后不可用时，系统 MUST 继续加载其他健康连接真实发现的工具，且 MUST NOT 为失败连接伪造工具。

#### Scenario: One managed connection is unavailable
- **WHEN** 用户同时启用了健康 MCP Server 和不可用 MCP Server
- **THEN** Agent MUST 只加载健康 Server 发现的真实工具，并继续可以调用它们

#### Scenario: All managed connections are unavailable
- **WHEN** 所有启用 MCP Server 的发现均失败
- **THEN** Agent MUST 不加载 MCP 工具，且不得生成虚构工具或证据

### Requirement: MCP readiness reports per-server state

MCP readiness SHALL 返回每个配置 Server 的安全可用状态、endpoint、工具数量和安全错误，并保留聚合可用状态。

#### Scenario: Readiness has partial MCP availability
- **WHEN** readiness 检查同时发现健康和故障 MCP Server
- **THEN** 结果 MUST 保留健康 Server 状态和失败 Server 的安全错误，且聚合状态 MUST 表示仍有可用 MCP 工具
