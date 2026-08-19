## Why

聊天 Agent 下一轮仅收到 user/assistant 正文，已持久化的工具结果、压缩证据指针和 citation 不会进入模型上下文。跨轮排障因此丢失已获得的证据，Agent 容易重复检索或给出脱离证据链的结论。

## What Changes

- 将 owner/session 范围内最近完成的工具审计摘要和历史 citation 作为受预算限制的跨轮证据上下文注入后续 Agent 请求。
- 保留压缩工具输出的 `evidenceId`，使 Agent 需要细节时继续使用既有受控读取工具。
- 修复压缩证据仓库中遗留的错误诊断审计方法，保持其仅提供聊天证据操作。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `stream-rag-chat`: 后续聊天请求包含 owner/session 范围内的可追溯工具证据摘要和 citation

## Impact

- 影响聊天流服务、工具审计查询与聊天回归测试。
- 不新增 API、数据库表或依赖。
