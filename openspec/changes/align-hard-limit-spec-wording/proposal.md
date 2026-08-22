## Why

主规格 `chat-memory-management` 的 "Context hard limit" 描述为"达到 95% 一律拒绝并要求手动压缩"，与实现不符——实现是先内联压缩（超时与预算约束内）、仍超限（或压缩失败）才拒绝。属于行为未变的文档漂移同步。

## What Changes

- 主 spec `openspec/specs/chat-memory-management/spec.md` 更新 95% 语义：先尝试内联压缩，仍超限/压缩失败才阻止；场景拆为"压缩后拒绝"与"压缩失败拒绝"
- 同步 `defer-chat-memory-compaction` change 的 MODIFIED 块（场景名与主 spec 一致）
- `maybe_compress_tool_output` docstring 修正为 tokenizer 优先（原"characters / 4"过时）

## Capabilities

纯文档/规格同步，无行为变更，`skip_specs: true`。

## Impact

- openspec/specs/chat-memory-management/spec.md
- openspec/changes/defer-chat-memory-compaction/specs/chat-memory-management/spec.md
- apps/backend/src/super_ai/chat/memory.py（docstring）
