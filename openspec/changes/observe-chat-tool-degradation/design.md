## Context

工具审计仓储和压缩摘要都是非关键路径：失败后聊天应继续。但当前 `except Exception` 直接返回或 pass，使这些降级完全不可见。项目已有 `emit_event`，其 JSON 序列化会脱敏字段。

## Goals / Non-Goals

**Goals:**

- 审计写入失败与压缩采样回退都产生可检索的结构化事件
- 事件不含工具参数、工具输出、异常消息或原始日志
- 保持当前聊天 SSE 与采样回退语义

**Non-Goals:**

- 不将非关键审计失败升级为聊天错误
- 不改造全局 `/metrics` 或引入新的 metrics 依赖
- 不重试审计写入，避免在请求路径额外放大负载

## Decisions

- 审计异常发出 `chat.tool_audit.failed`，字段仅含工具名、工具事件状态和异常类别
- 工具压缩未产生摘要时发出 `chat.tool_compression.fallback`，字段仅含工具名、`sampled_fallback` 模式与原因类别
- 两个事件均使用现有 `emit_event`，以复用 request correlation 和字段脱敏

## Risks / Trade-offs

- 失败高频时会产生较多日志；这是发现持久化或模型依赖故障所需的最小信号，后续可在日志后端聚合告警

## Migration Plan

1. 部署后立即增加事件，无数据迁移
2. 回滚仅停止额外日志，不影响聊天或历史数据
