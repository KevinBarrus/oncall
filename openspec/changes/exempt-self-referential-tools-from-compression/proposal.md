## Why

`read_tool_output_evidence` 返回被压缩工具输出的**原文**，却被自身的压缩包装再次压缩成摘要并生成新 evidenceId——证据展开机制对唯一目标场景（大输出）完全失效，且每次展开写入重复 evidence 行。`load_skill` 返回 SKILL.md 指令原文，压缩同样破坏指令语义。

## What Changes

- 新增 `_NO_COMPRESSION_TOOL_NAMES = frozenset({"read_tool_output_evidence", "load_skill"})`
- `_wrap_tool_output_compression` 对这些工具直接返回原样（不替换 coroutine）
- 回归测试：展开结果与 evidence.content 完全相等；load_skill 原文保留；普通大输出工具仍被包装

## Capabilities

压缩包装豁免名单语义，`skip_specs: true`。

## Impact

- chat/streaming.py（常量 + wrapper 前置判断）
- tests/test_chat_memory.py（3 个回归测试）
