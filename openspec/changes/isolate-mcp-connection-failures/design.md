## Context

`LocalMcpClient.discover_tools()` 依次发现全部连接的工具，但单个 `_run_connection()` 失败会直接终止循环。问题 16 已让会话按 Server 复用；本变更只补充连接级故障隔离。

## Goals / Non-Goals

**Goals:**

- 一个连接故障时继续使用其他连接发现的真实工具
- 让 readiness 暴露不含凭据的逐连接结果
- 保留当前工具调用超时、重试、审计和失败语义

**Non-Goals:**

- 不缓存失败结果或新增熔断器
- 不改变用户显式“检查连接”接口的失败语义
- 不伪造故障连接的工具定义

## Decisions

- 在 `discover_tools()` 内逐连接捕获 `McpClientError`，保存安全错误文本，并继续下一个连接；成功工具仍构成短 TTL 缓存
- 用同一轮逐连接发现结果构造 readiness：总状态只在至少一个连接可用时为真，`servers` 数组保留 name、endpoint、toolCount、ok、error
- 调用保留既有 provider 路由：已注册工具调用其所属连接，失效时由该连接返回 `McpClientError`

## Risks / Trade-offs

- 所有连接不可用时工具列表为空，Agent 无 MCP 工具可用；这是避免伪造工具的正确降级
- readiness 不保存连接历史状态，下一次检查会重试；需要抑制持续故障时再引入单独熔断策略

## Migration Plan

1. 部署后按下一次发现生效，无数据迁移
2. 回滚代码即可恢复全量失败语义，不遗留持久化状态
