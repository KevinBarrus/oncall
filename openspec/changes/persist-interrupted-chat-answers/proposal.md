## Why

聊天流中断时（异常/上下文超限）已生成的 partial 回答被丢弃——用户消息已持久化但回答消失，对话历史出现"有问无答"，刷新后前端已渲染内容丢失。

## What Changes

- 流异常路径（`ChatRuntimeContextLimitReached` 与通用 `Exception`）若 `answer_parts` 非空，持久化一条带 `interrupted: true` 标记的 assistant 消息再发 error 事件
- 契约 `ChatMessageMetadata` 增加可选 `interrupted?: boolean`
- 更新既有测试语义（safe error 测试改为断言 partial 回答已持久化）+ 新增回归测试

## Capabilities

流中断 partial 回答持久化，`skip_specs: true`。

## Impact

- chat/streaming.py（`_persist_interrupted_answer` + 两个异常分支）
- packages/api-contracts/src/chat.ts（metadata 可选字段）
- tests/test_stream_rag_chat_api.py（新增 + 更新）
