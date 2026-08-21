## Context

solution3.md 问题22：前端 SSE 无重连。方案：补 onerror 重连；断点续传（sequence + from_sequence）可选。

## Goals / Non-Goals

**Goals:**

- 连接建立前（fetch 阶段）网络失败自动重试
- 非 2xx 服务端错误立即暴露（不吞错误）

**Non-Goals:**

- 不实现断点续传（`from_sequence` 需后端事件缓存与重放，成本高；chat 流有会话执行租约，续传需重放 Agent 状态）
- 不在流开始后自动重发 POST（会重复执行 Agent、重复持久化消息）

## Decisions

- 重试仅覆盖"获取 response + 2xx 检查"阶段；读取循环开始后中断不重试（上层已有"回答流意外中断"检测与 aiops 后台任务兜底）
- 非 2xx 抛 `ApiClientError` 立即上抛（服务端明确错误无重试价值）
- 重试每次重新取 token（`getAccessToken` 每次调用），兼容刷新

## Risks / Trade-offs

- [fetch 失败时服务端可能已处理] → 概率低；chat 流有会话租约（BUSY 防并发），重试请求最多得到 BUSY 而非重复执行
- [重试延迟 500ms/1s] → 对连接建立阶段可接受

## Migration Plan

无契约变更。
