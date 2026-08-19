## Context

`ToolRegistry` 在 MCP 工具重名或与本地工具重名时生成 `mcp__<server>__<tool>`，但保留了原始 description。LangChain 将该 description 直接暴露给 Agent，因此模型看不到限定名的含义。

## Goals / Non-Goals

**Goals:**

- 让重名 MCP 工具的 Agent 可见 description 说明 provider、原始名和限定名
- 保留现有工具名、schema 和执行路由

**Non-Goals:**

- 不拒绝合法的跨 Server 同名工具
- 不改写 MCP Server 提供的原始业务描述
- 不增加模型选择器或额外元数据协议

## Decisions

- 只在实际生成限定名时追加一段固定路由说明；未冲突工具保持原 description，避免噪声
- `ToolDefinition.description` 与 `StructuredTool.description` 共用该结果，避免两份 Agent 视图漂移

## Risks / Trade-offs

- 限定描述会略微增加重名工具的上下文 token；仅冲突时追加，成本有界

## Migration Plan

1. 部署后新装配的 Agent 工具即时使用新描述
2. 回滚代码即可恢复原描述，无数据迁移
