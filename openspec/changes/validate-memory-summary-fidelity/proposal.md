## Why

记忆压缩只校验摘要的 JSON 结构、summary 长度和 sourceMessageIds 归属，不校验摘要内容是否忠实于原文。模型把数字、错误码或决策、待办总结错时，系统无法察觉，错误的摘要会作为后续 Agent 上下文继续被引用。

## What Changes

- 在结构校验通过后，对压缩记忆执行确定性的忠实性校验
- 校验摘要与条目中的数字可追溯到压缩原文，decision 与 todo 条目需与原文存在字面证据
- 校验失败抛出专用异常，保留上一版记忆，不覆盖已有摘要

## Capabilities

### Modified Capabilities

- `chat-memory-management`: 压缩摘要增加忠实性校验，失败不覆盖已有记忆

## Impact

- 聊天记忆服务与忠实性校验辅助函数
- 聊天记忆回归测试、OpenSpec WIKI 与问题 15 记录
