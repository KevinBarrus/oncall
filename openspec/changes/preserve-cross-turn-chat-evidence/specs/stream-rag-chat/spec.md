## ADDED Requirements

### Requirement: Cross-turn chat evidence context
流式聊天服务 SHALL 在后续请求中向 Agent 提供当前 owner 和聊天会话范围内最近完成的工具结果摘要、压缩证据指针和已保存 citation 的受限上下文。该上下文 MUST 不包含其他 user 或会话的内容，并 MUST 保持在预定大小限制内。

#### Scenario: Follow-up request receives prior tool evidence
- **WHEN** 当前会话的前一轮聊天已完成工具调用并保存了审计结果或 citation，user 发送后续问题
- **THEN** Agent MUST 收到可识别工具名称、结果摘要、`evidenceId`（如有）和 citation 标识的上下文

#### Scenario: Session evidence stays isolated
- **WHEN** 另一 user 或另一会话保存了工具审计或 citation
- **THEN** 当前聊天请求 MUST NOT 接收该证据上下文
