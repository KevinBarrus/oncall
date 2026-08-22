## Why

`count_tokens` 每次调用新建 ChatModel（含 tokenizer 初始化开销），`_select_messages_for_compaction` 对前缀逐条估算 → 长会话压缩时数百到数千次模型构造 + 编码，O(n²) 放大，用户可感知延迟。

## What Changes

- `QwenOpenAIProvider` 惰性缓存 token 计数模型（`_token_counter_model`，首次 `count_tokens` 时创建一次）

## Capabilities

token 计数模型复用，`skip_specs: true`。

## Impact

- llm/provider.py（缓存字段 + count_tokens 复用）
