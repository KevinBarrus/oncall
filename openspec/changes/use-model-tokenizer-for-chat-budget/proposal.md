## Why

聊天上下文、摘要输入和工具输出目前使用不同的近似计数方式，中文日志会被低估，导致压缩阈值和上下文保护不能可靠生效。需要统一为与当前模型兼容的计数策略，并在无法获得 tokenizer 时保持保守。

## What Changes

- 为聊天上下文预算提供统一 token 计数入口，优先使用当前模型的 tokenizer。
- 将工具输出压缩阈值和 Agent 运行时预算改用该入口。
- tokenizer 不可用时采用保守回退估算，避免低估中文内容。

## Capabilities

### New Capabilities

- 无

### Modified Capabilities

- `chat-memory-management`: 聊天记忆、工具输出和运行时预算必须使用一致且保守的 token 计数。

## Impact

- 影响 `apps/backend/src/super_ai/chat/memory.py` 与现有聊天记忆测试。
- 不改变 API 或持久化模型，不新增依赖。
