## MODIFIED Requirements

### Requirement: Compression preserves full history
记忆压缩 SHALL 只改变模型上下文的摘要和边界，MUST NOT 删除或改写原始聊天消息；已被摘要覆盖的消息 MUST 从运行时热历史迁入可追溯归档，模型请求 MUST NOT 重新加载该归档历史。

#### Scenario: User reads compressed session
- **WHEN** user 读取已经执行过压缩的会话历史
- **THEN** API MUST 返回压缩前后所有原始消息，模型请求 MUST 只包含摘要和活跃消息
