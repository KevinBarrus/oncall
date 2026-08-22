## Why

solution3 问题3 声明的"压缩降级 compressionFailed 标记"仅实现于字符串输出路径；知识检索等走结构化路径的工具在 sampled_fallback 降级时无法通过审计 `result_summary` 查询到降级事实，可观测目标对主路径落空，且两处元数据构造逻辑重复不一致。

## What Changes

- `maybe_compress_structured_tool_output` 复用 `tool_output_compression_metadata` 构造 `_compression`，`mode == "sampled_fallback"` 时补 `compressionFailed: True`
- 回归测试：结构化降级路径带标记、llm_summary 成功路径不带标记

## Capabilities

结构化压缩降级可观测标记，`skip_specs: true`。

## Impact

- chat/memory.py（结构化路径 metadata 复用 + compressionFailed）
- tests/test_chat_memory.py（1 个回归测试）
