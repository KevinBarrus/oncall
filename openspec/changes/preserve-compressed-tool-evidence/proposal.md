## Why

工具输出压缩后只有摘要和哈希，AIOps Agent 不能按需核验决定性日志或结构化字段，故障证据不可逆。需要保存受权限保护的原始输出，并让模型和用户通过引用按需展开。

## What Changes

- 持久化被压缩工具输出的原文及其压缩元数据。
- 在压缩结果中返回稳定 evidence ID，而非原文。
- 提供 owner/session 作用域的证据读取 API 和 Agent 工具。

## Capabilities

### New Capabilities

- `compressed-tool-evidence`: 压缩工具输出的可追溯原文证据与受控展开。

### Modified Capabilities

- `agent-tool-call-audits`: 工具审计关联压缩输出的可追溯证据。

## Impact

- 影响聊天工具包装、SQLite 模型与仓储、Alembic、API 合同和聊天测试。
