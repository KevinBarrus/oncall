## MODIFIED Requirements

### Requirement: Manual compression
使用 `manual` 的会话 SHALL 仅在 user 应用该模式或显式请求压缩时投递一次可查询的后台压缩任务，不得按轮数或 70% 阈值自动压缩；请求路径 MUST NOT 循环压缩全部未压缩历史。

#### Scenario: Applying manual mode compresses immediately
- **WHEN** user 将一个会话的记忆模式应用为 `manual`
- **THEN** 后端 MUST 投递一次压缩任务并立即返回当前记忆状态与任务状态，不得等待任务完成

#### Scenario: Manual mode can be compressed again
- **WHEN** manual 会话在产生更多消息后收到显式压缩请求
- **THEN** 后端 MUST 投递一次压缩任务，任务完成时 MUST 合并已有摘要和一个受输入预算限制的新历史批次
