## Context

solution4.md 问题14（P2，文档）：`spec.md:60-69` 描述"95% 一律拒绝并要求手动压缩"；实现（`chat/memory.py:156-196`）是先内联压缩、失败才拒绝。另 `maybe_compress_tool_output` docstring 仍写 "characters / 4"（已用 tokenizer 优先）。

## Goals / Non-Goals

**Goals:**

- 规格文本与可执行实现一致（95% 先内联压缩、仍超限/失败才拒绝）
- docstring 反映真实 token 计数策略

**Non-Goals:**

- 不改变任何运行时行为（实现已是事实来源，只同步文档）

## Decisions

- 主 spec 的 Requirement 改为"先尝试内联自动压缩；压缩后仍达 95%（或压缩失败）时阻止"；原 "Backend rejects bypass attempt" 场景拆为 "Backend compacts inline before rejecting" 与 "Backend rejects when inline compaction fails" 两个场景（openspec 要求 MODIFIED 替换整块，场景名需覆盖主 spec 现存场景）
- 同步 defer-chat-memory-compaction change 的 MODIFIED 块（该 change 曾 MODIFIED "Context hard limit"，主 spec 场景改名后 archive 校验失败）；同时把其 Thirty-turn 场景名与主 spec 对齐（pre-existing 校验失败顺手修正，语义保留 defer 措辞）
- docstring 改为 "Token count prefers the configured model's tokenizer, falling back to a safe Unicode estimate"

## Risks / Trade-offs

- [openspec validate --all 仍 1 failed] → `unify-agent-tool-registry` 为残缺 untracked 遗留目录（无 .openspec.yaml），pre-existing，非本任务范围

## Migration Plan

无。
