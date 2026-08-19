## Purpose

为受管理 MCP 连接提供可复用的运行时会话和工具定义缓存，降低聊天与诊断中重复握手带来的延迟和资源开销。

## ADDED Requirements

### Requirement: Managed MCP sessions are reused
系统 SHALL 在应用运行期按用户当前启用连接配置复用 MCP 运行时会话，并在连接配置改变或应用关闭时关闭旧会话。

#### Scenario: 同一配置连续调用工具
- **WHEN** 同一用户以未变化的启用连接配置连续调用同一 MCP Server 的工具
- **THEN** 系统 MUST 使用已初始化的 Server 会话执行后续调用，而不是重新握手

#### Scenario: 连接配置发生改变
- **WHEN** 用户的启用 MCP 连接配置与已缓存客户端不一致
- **THEN** 系统 MUST 关闭旧客户端会话并使用新配置创建客户端

### Requirement: MCP tool discovery is cached briefly
系统 SHALL 缓存成功发现的 MCP 工具定义一段有限时间；调用失败或缓存过期后 MUST 重新发现。

#### Scenario: 缓存有效
- **WHEN** 同一客户端在缓存有效期内重复装配工具
- **THEN** 系统 MUST 复用已发现的工具定义

#### Scenario: Server 会话失败
- **WHEN** 已复用的 Server 会话调用失败
- **THEN** 系统 MUST 丢弃该会话，并依照该连接的既有重试语义重新建立会话
