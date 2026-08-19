## ADDED Requirements

### Requirement: Database-scoped chat execution lease
流式聊天服务 SHALL 在执行 Agent 前获取 owner 和会话范围的数据库执行租约，并在终止时释放。无法获取租约时 MUST 返回明确的会话繁忙错误，不得执行或持久化该请求。

#### Scenario: Concurrent requests across workers
- **WHEN** 两个服务实例同时处理同一 owner 和会话的聊天请求
- **THEN** 仅一个请求 MUST 执行，另一个 MUST 收到会话繁忙错误
