## ADDED Requirements

### Requirement: Deferred chat memory job handling
Runtime SHALL 执行 owner 范围的聊天记忆压缩任务，并沿用既有的持久化任务超时、重试、租约和终态语义。

#### Scenario: Deferred compaction succeeds
- **WHEN** 已投递的聊天记忆压缩任务被 worker 领取
- **THEN** worker MUST 仅更新该 owner 和会话的记忆状态，并保留原始聊天消息

#### Scenario: Deferred compaction fails
- **WHEN** 聊天记忆压缩任务因模型调用或摘要格式失败
- **THEN** Runtime MUST 按既有任务失败语义记录失败，且 MUST NOT 破坏该会话已有记忆状态
