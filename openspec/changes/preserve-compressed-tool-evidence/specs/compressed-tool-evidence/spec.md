## Purpose

为压缩后的聊天工具输出保留受 owner 和会话范围保护的原始证据，使 Agent 能在不重新注入全部日志的前提下按需核验细节。

## ADDED Requirements

### Requirement: Compressed output has retrievable evidence
系统 SHALL 为每个被压缩的聊天工具输出保存原始内容、压缩元数据和稳定 evidence ID。压缩后的模型输入 MUST 包含 evidence ID，MUST NOT 包含完整原始输出。

#### Scenario: Large tool output is compressed
- **WHEN** 聊天工具输出超过压缩阈值
- **THEN** 系统 MUST 保存 owner/session 作用域的原始输出，并在压缩结果中返回 evidence ID

### Requirement: Evidence access is owner and session scoped
系统 SHALL 仅允许会话 owner 通过关联会话读取原始证据。

#### Scenario: Owner expands evidence
- **WHEN** 会话 owner 请求该会话的 evidence ID
- **THEN** 系统 MUST 返回原始输出及其压缩元数据

#### Scenario: Other user requests evidence
- **WHEN** 非 owner 请求 evidence ID
- **THEN** 系统 MUST 拒绝请求且不得暴露原始输出

### Requirement: Agent can expand evidence on demand
聊天 Agent SHALL 获得一个仅能读取当前会话证据的工具。

#### Scenario: Agent needs omitted detail
- **WHEN** Agent 从压缩工具结果中获得 evidence ID 并需要核验细节
- **THEN** Agent MUST 能调用展开工具取得该证据原文
