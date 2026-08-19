## Purpose

让手动发起的聊天记忆压缩脱离 HTTP 请求等待路径，并向调用方提供可查询的持久任务状态，避免长会话操作阻塞。

## ADDED Requirements

### Requirement: Manual compaction returns a durable job
系统 SHALL 在 user 切换到 `manual` 模式或显式请求压缩时投递 owner 范围的聊天记忆压缩任务，并在响应中返回该任务和当前会话状态。

#### Scenario: User applies manual mode
- **WHEN** user 将一个会话的记忆模式更新为 `manual`
- **THEN** 系统 MUST 返回已投递的聊天记忆压缩任务，且不得等待摘要模型完成

#### Scenario: User explicitly compacts a session
- **WHEN** user 请求压缩其 manual 会话
- **THEN** 系统 MUST 返回已投递的聊天记忆压缩任务，且该任务仅属于该 user 与会话
