## ADDED Requirements

### Requirement: User-visible chat memory compaction jobs
系统 SHALL 将用户手动触发的聊天记忆压缩作为既有 durable background job 返回，并允许 user 使用既有任务查询接口读取其状态。

#### Scenario: Returned job can be queried
- **WHEN** 手动记忆压缩接口返回一个任务
- **THEN** 该任务 MUST 使用既有 owner 范围权限控制，并可通过后台任务查询接口读取状态
