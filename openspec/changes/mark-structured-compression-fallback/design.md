## Context

solution4.md 问题4（P2，回归：solution3 问题3 部分）：字符串路径（streaming.py:788-789）在 `mode == "sampled_fallback"` 时设 `compressionFailed: True`；结构化路径（memory.py:437-443）只有 mode/sourceHash/originalChars/compressedChars。知识检索工具返回 dict 走结构化路径，是主要降级场景。

## Goals / Non-Goals

**Goals:**

- 结构化路径 sampled_fallback 时 `_compression.compressionFailed == True`
- 消除两处 metadata 构造重复（复用 `tool_output_compression_metadata`）

**Non-Goals:**

- 不改变字符串路径行为（已正确）
- 不改变 LLM 压缩/采样回退逻辑

## Decisions

- 结构化路径构造 metadata 改为调用 `tool_output_compression_metadata(encoded, compressed, mode=mode)`（与字符串路径一致），仅 `sampled_fallback` 时补 `compressionFailed: True`（成功路径不带该键，与字符串路径一致）
- 回归测试用 FailingProvider（LLM 抛错）触发降级断言标记，另断言 llm_summary 成功路径不带标记

## Risks / Trade-offs

- [metadata 键集合变化影响消费方] → 仅新增条件键，审计/前端读取不破坏（可选键语义）

## Migration Plan

无 schema 变更。
