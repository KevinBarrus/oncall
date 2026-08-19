## Why

聊天工具审计写入和大输出压缩会安全降级，但当前异常被静默吞掉。运维者无法区分正常结果、审计缺失和采样压缩，导致可审计性和故障排查能力下降。

## What Changes

- 审计持久化失败时发出脱敏结构化事件，同时继续聊天流
- 工具输出压缩使用采样回退时发出脱敏结构化事件
- 为两个降级路径补充回归测试，确保不记录工具内容或异常正文

## Capabilities

### New Capabilities

- 无

### Modified Capabilities

- `stream-rag-chat`: 审计降级必须可观测且不得中断聊天
- `chat-memory-management`: 工具输出压缩回退必须可观测且不得泄露原始内容

## Impact

- 影响聊天流、记忆压缩、后端测试、问题追踪和 OpenSpec WIKI
- 不改变 HTTP、SSE、数据库 schema 或新增依赖
