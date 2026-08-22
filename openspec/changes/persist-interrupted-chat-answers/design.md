## Context

solution4.md 问题13（P2，确认项）：`streaming.py:399-408` 异常路径丢弃 `answer_parts`；用户消息已持久化。

## Goals / Non-Goals

**Goals:**

- 流中断时已生成回答不丢失（持久化带 `interrupted` 标记的 assistant 消息）
- error SSE 事件语义不变

**Non-Goals:**

- 不做前端 interrupted 展示（数据完整性是本问题核心；前端已有"回答流意外中断"提示）
- 不重试 Agent 执行（重发 POST 会重复持久化，既定取舍）

## Decisions

- 新增 `_persist_interrupted_answer`：`"".join(answer_parts).strip()` 非空才持久化；metadata 含 citations/reasoning/toolCallIds + `interrupted: True`；持久化自身失败仅 emit `agent.chat.partial_persist_failed`（不掩盖原始错误）
- 两个异常分支（上下文超限 / 通用异常）在发 error 事件前调用
- 契约 `ChatMessageMetadata` 加可选 `interrupted?: boolean`（前端类型完整，无人访问不破坏）
- 既有 `test_streaming_chat_emits_safe_error_without_partial_assistant_message` 更新为新语义（partial 已持久化），另新增中断场景回归测试

## Risks / Trade-offs

- [partial 消息可能是不完整句子] → 带 `interrupted` 标记可由前端/用户识别，优于"有问无答"
- [内容含敏感值] → 消息内容为模型生成（用户会话内数据），不改变既有持久化脱敏边界

## Migration Plan

无。
