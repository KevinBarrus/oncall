## ADDED Requirements

### Requirement: Chat session execution lease repository
聊天会话 Repository SHALL 使用 owner 范围条件更新获取和释放带 token 的短期执行租约。

#### Scenario: Lease owner releases execution
- **WHEN** 持有有效 token 的聊天执行结束
- **THEN** Repository MUST 释放该会话租约，后续请求可以获取它
