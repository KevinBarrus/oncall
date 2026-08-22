## MODIFIED Requirements

### Requirement: Thirty-turn automatic compression
使用 `every_30_turns` 的会话 SHALL 在自上次压缩边界起完成 30 轮 user-assistant 对话后投递旧上下文压缩。当前候选上下文低于硬限时，自动压缩 MUST NOT 阻塞下一次模型调用。

#### Scenario: Thirty completed turns trigger compression
- **WHEN** 默认模式会话在压缩边界之后已有至少 30 条 assistant 消息并发送下一条消息，且候选上下文低于硬限
- **THEN** 后端 MUST 投递压缩任务并使用原始历史调用 Agent

### Requirement: Seventy-percent automatic compression
使用 `context_70_percent` 的会话 SHALL 在包含待发送消息的估算上下文达到窗口 70% 时投递旧上下文压缩。候选上下文未到硬限时，系统 MUST 继续调用 Agent，不得等待摘要完成。

#### Scenario: Candidate context reaches threshold
- **WHEN** 待发送消息会使会话估算占用达到或超过 70% 且低于硬限
- **THEN** 后端 MUST 投递可压缩历史的摘要任务并继续本次聊天流

### Requirement: Context hard limit
系统 SHALL 在候选上下文占用达到或超过 95% 时尝试一次受超时限制的同步压缩；压缩后仍达到或超过 95% 时，系统 MUST 阻止新增聊天消息。

#### Scenario: Frontend blocks at hard limit
- **WHEN** 当前会话 `contextUsagePercent` 达到或超过 95
- **THEN** 前端 MUST 禁用输入和发送并显示执行手动压缩的中文提示

#### Scenario: Backend compacts inline before rejecting
- **WHEN** 客户端提交会使上下文占用达到或超过 95% 的消息，且同步压缩成功但压缩后仍达到或超过 95%
- **THEN** 后端 MUST 返回统一上下文上限错误且 MUST NOT 持久化该消息

#### Scenario: Backend rejects when inline compaction fails
- **WHEN** 客户端提交会使上下文占用达到或超过 95% 的消息，且同步压缩失败（LLM 不可用、摘要无效或超时）
- **THEN** 后端 MUST 在会话状态记录压缩失败原因，并返回统一上下文上限错误，MUST NOT 持久化该消息
