## Why

`clear_messages` 只删消息并重置记忆状态，`compressed_tool_evidence`（保存未压缩完整工具原文，无大小上限）与工具审计行永久残留且持续增长；每次压缩调用新增 evidence 行，无 `source_hash` 去重。

## What Changes

- `clear_messages` 事务内一并删除会话关联的 `compressed_tool_evidence` 与 `tool_call_audits` 行
- `SQLiteCompressedToolEvidenceRepository.create` 按 `(会话, source_hash)` 去重，同 hash 返回已有行

## Capabilities

证据/审计生命周期随会话清空清理 + 证据写入去重，`skip_specs: true`。

## Impact

- memory/sqlite.py（clear_messages 清理 + evidence create 去重）
- tests/test_memory_repositories.py（1 个回归测试）
