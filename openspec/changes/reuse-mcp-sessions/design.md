## Context

当前 `LocalMcpClient` 的发现和调用均通过临时上下文建立 MCP 会话；`McpConnectionService` 又会为每次装配创建新的客户端。LangChain MCP adapter 还会绕过本地客户端直接执行工具。详见 proposal.md。

## Goals / Non-Goals

**Goals:**

- 每个用户连接配置在单个应用进程内复用客户端、工具发现结果和每个 Server 的会话
- 当连接配置变化、调用失败或应用停止时显式释放资源
- 保持现有真实工具、超时、重试、审计及用户隔离语义

**Non-Goals:**

- 不跨进程共享 MCP 连接
- 不引入通用连接池或新的依赖
- 不改变 MCP 管理 API 或对外 SSE 契约

## Decisions

- `McpConnectionService` 用 owner 与完整启用连接配置作为缓存键。每次读取配置后比较键；不一致即关闭并替换旧客户端。相比无限 TTL 的按用户缓存，这样能自然处理编辑、启停和删除
- `LocalMcpClient` 每个 Server 持有一个串行会话和短 TTL 的成功发现缓存。MCP session 在同一连接上串行执行，避免并发请求争用协议流；这是最小的固定上限（一条会话/Server）
- `ToolRegistry` 根据真实发现的 JSON schema 创建包装工具，并将执行统一路由回 `McpToolExecutor`。不再使用 `MultiServerMCPClient` 创建的工具，以免绕过会话复用
- 连接调用异常后关闭该 Server 会话再按既有重试次数重连。保留现有 timeout/retry 配置

## Risks / Trade-offs

- [单 Server 同时调用被串行化] → 一条 MCP 会话通常要求顺序读写；需要更高吞吐时再增加经验证的多会话池
- [长时间空闲连接被 Server 断开] → 首次后续调用失败时关闭并重连，调用方仍使用既有重试语义
- [进程重启不复用连接] → 这是有意的进程边界；应用 lifespan 关闭时主动释放本进程资源

## Migration Plan

1. 部署后客户端按需建立，无数据迁移
2. 回滚代码即可停止复用；不会遗留持久化状态
