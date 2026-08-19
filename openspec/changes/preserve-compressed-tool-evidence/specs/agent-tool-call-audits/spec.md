## ADDED Requirements

### Requirement: Compressed audit results remain traceable
工具调用审计 SHALL 在结果被压缩时保留其 evidence ID 和压缩元数据，使审计使用者能够关联受控原文证据。

#### Scenario: Audit contains compressed result metadata
- **WHEN** 工具调用输出被压缩
- **THEN** 审计结果摘要 MUST 包含 evidence ID 和原始输出哈希
