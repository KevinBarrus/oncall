## MODIFIED Requirements

### Requirement: Streaming chat tool calls are audited

流式聊天服务 SHALL 为每个 Agent `tool.call` 事件保留一个 owner 范围的审核生命周期，同时继续发出现有的共享 SSE 事件序列。审计持久化失败时，服务 MUST 发出不含工具参数、输出或异常正文的结构化降级事件，并继续聊天流。

#### Scenario: 开始事件创建聊天审核记录
- **WHEN** 该聊天 Agent 会发出一个 `tool.call` 事件，状态为 `started`
- **THEN** 该服务 MUST 在发出相应的 SSE 帧之前，会创建与当前聊天会话相关的审核记录。

#### Scenario: Terminal event finalizes chat audit record
- **WHEN** 该聊天 Agent 会发出带有 `completed` 或 `failed` 状态的 `tool.call` 事件
- **THEN** 该服务 MUST 最终确定匹配的审计记录，并带有绑定结果或错误摘要，然后发出相应的 SSE 帧。

#### Scenario: Audit persistence does not suppress chat output
- **WHEN** 审计持久化应独立于 Agent 的执行失败
- **THEN** 服务 MUST 保留聊天 SSE 的生命周期和最终答案处理。

#### Scenario: Audit persistence degrades safely
- **WHEN** 审计仓储在创建或最终确定时失败
- **THEN** 服务 MUST 发出带工具名、事件状态和异常类别的安全结构化事件，并继续既有聊天 SSE 生命周期。
