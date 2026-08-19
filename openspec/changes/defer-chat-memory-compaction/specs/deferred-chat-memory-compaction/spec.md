## Purpose

定义聊天记忆自动压缩的异步执行与硬限兜底，使摘要服务暂时不可用时仍能在安全预算内完成聊天请求。

## ADDED Requirements

### Requirement: Deferred automatic memory compaction
系统 SHALL 将 30 轮和 70% 阈值触发的自动聊天记忆压缩持久化为后台任务；在任务尚未完成且候选上下文未到硬限时，系统 MUST 使用未压缩历史继续当前聊天流。

#### Scenario: Automatic threshold schedules background work
- **WHEN** 会话达到自动压缩阈值但候选上下文低于硬限
- **THEN** 系统 MUST 投递该会话的压缩任务，并继续当前聊天请求而不等待摘要模型调用

### Requirement: Compression failure degrades safely
系统 SHALL 在摘要模型超时、调用失败或返回无效结构时保留既有记忆和压缩边界，并记录可观测事件；候选上下文仍在硬限内时 MUST 继续聊天请求。

#### Scenario: Summary generation fails below hard limit
- **WHEN** 记忆压缩失败且候选上下文低于硬限
- **THEN** 系统 MUST 不更新记忆状态，并继续处理该聊天消息

### Requirement: Hard-limit synchronous fallback
系统 SHALL 在候选上下文到达硬限前仅执行一次受超时限制的同步压缩尝试；若仍不能释放足够预算，MUST 拒绝新增消息且不得持久化该消息。

#### Scenario: Background compaction cannot finish before hard limit
- **WHEN** 候选上下文达到硬限且尚无可用的压缩结果
- **THEN** 系统 MUST 尝试一次有超时的同步压缩，并仅在压缩后仍超限时返回上下文上限错误
