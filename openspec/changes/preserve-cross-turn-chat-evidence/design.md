## Context

聊天消息的 metadata 已保存 citation 和工具调用 ID，工具审计保存了结构化参数与结果摘要，压缩原文也已有 owner/session 隔离的 `evidenceId`。但 Agent 适配器只传递消息正文。

## Goals / Non-Goals

**Goals:**
- 在不重放完整工具输出的前提下保留跨轮证据链
- 使用既有 owner/session 查询边界和证据展开工具
- 为模型上下文设置固定上限

**Non-Goals:**
- 不做语义检索、向量化或新增证据表
- 不重放 LangChain 原生 tool message
- 不改变 SSE 或 HTTP 契约

## Decisions

### 注入最近的持久化摘要

聊天服务读取本会话最近完成的工具审计与历史 assistant metadata，格式化成单段系统上下文。结果摘要已受审计长度限制，citation 只保留 ID、标题与来源。压缩结果中的 `evidenceId` 直接保留，以便模型使用已有工具按需读取原文。

替代方案是重放原始 tool message；它会显著抬高 token 并依赖 LangChain 内部消息格式，因此不采用。

### 固定条数和字符预算

仅保留最近 6 条完成审计、最近 8 个 citation，并将每项摘要裁剪到 400 字符，总上下文不超过 4,000 字符。该限制使上下文预算可预测；更复杂的相关性排序留待有真实质量数据后再做。

## Risks / Trade-offs

- [旧证据未被选入] → 保留最近窗口和 `evidenceId`，避免无限增长
- [审计写入失败] → 当前聊天仍可使用历史 citation，不伪造工具结果
