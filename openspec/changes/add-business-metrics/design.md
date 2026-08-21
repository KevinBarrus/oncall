## Context

solution3.md 问题23：`/metrics` 缺业务指标。方案：补充 chat 请求数、平均上下文 token、压缩触发次数、MCP 调用延迟。

## Goals / Non-Goals

**Goals:**

- `/metrics` 暴露方案列出的四类业务指标
- 指标记录点不侵入领域代码（模块级 registry，类比 `emit_event`）

**Non-Goals:**

- 不引入 Prometheus 客户端库/格式（现有 JSON 端点保持，监控栈可抓取转换）
- 不按会话/用户维度拆分（进程内聚合即可）

## Decisions

- `record_business_metric(name, amount=1)`：累加 total 并递增 samples；`snapshot_business_metrics` 输出 count/total/average（排序）
- 指标点：
  - `chat_streams`（streaming 入口）
  - `chat_context_tokens`（prepare_message 返回前，记录当前上下文 token）
  - `chat_compactions` / `chat_compaction_failures`（记忆压缩成功/失败）
  - `tool_compression_fallbacks`（工具输出压缩降级）
  - `mcp_tool_latency_ms`（MCP 工具成功调用延迟）
- `reset_business_metrics` 供测试隔离（autouse fixture）

## Risks / Trade-offs

- [模块级单例跨请求共享] → 与 `emit_event` 同模式；reset 仅测试使用，运行时持续累积
- [average 为简单均值] → 满足可观测需求，不引入直方图/分位数

## Migration Plan

无 schema 变更。
