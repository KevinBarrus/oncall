## Why

压缩 wrapper 中 `evidence_repository.create` 抛异常会直接冒泡出 `_compressed_coroutine`，LangChain 记为 `on_tool_error`——压缩内容已生成却因证据落库失败而丢弃，工具调用被报错，与 LLM 压缩失败→采样回退的尽力而为语义不一致。

## What Changes

- str 与 dict 两条 evidence 写入路径包 try/except：失败仅 emit `chat.tool_evidence.persist_failed` 事件（metadata 不含 evidenceId，模型仍使用压缩摘要）
- 回归测试：evidence create 抛错时工具调用仍返回压缩摘要且无 evidenceId

## Capabilities

evidence 落库失败隔离语义，`skip_specs: true`。

## Impact

- chat/streaming.py（两处 evidence 写入兜底）
- tests/test_chat_memory.py（1 个回归测试）
