## ADDED Requirements

### Requirement: Archived and active chat history queries
后端 SHALL 在仓库边界区分活跃聊天消息与归档聊天消息，并要求每种查询和归档操作均携带 owner user ID 与会话 ID。

#### Scenario: Runtime reads active history only
- **WHEN** 聊天运行时准备模型上下文
- **THEN** 仓库 MUST 仅返回该会话尚未归档的活跃消息

#### Scenario: Archive operations are owner scoped
- **WHEN** 系统归档、读取、清除或删除聊天历史
- **THEN** 仓库 MUST 仅影响提供的 owner 和会话范围内的消息
