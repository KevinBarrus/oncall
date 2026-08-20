## ADDED Requirements

### Requirement: Memory summary fidelity validation
记忆压缩 SHALL 在结构校验通过后，对摘要内容执行忠实性校验：摘要与条目中的数字 MUST 能追溯到压缩原文，decision 与 todo 条目 MUST 与原文存在字面证据。校验失败时后端 MUST 保留上一版记忆且 MUST NOT 覆盖已有摘要。

#### Scenario: Summary fabricates an untraceable number
- **WHEN** 压缩模型生成的摘要包含原文不存在的数字或数字错误码
- **THEN** 后端 MUST 拒绝该摘要、保留上一版记忆，且 MUST NOT 推进压缩边界

#### Scenario: Action item has no literal basis in the source
- **WHEN** decision 或 todo 条目内容与压缩原文无任何长度≥2 的非数字连续片段
- **THEN** 后端 MUST 拒绝该摘要并保留上一版记忆

#### Scenario: Faithful summary is accepted
- **WHEN** 摘要的数字均可追溯到原文且行动条目存在字面证据
- **THEN** 后端 MUST 接受该摘要并更新会话记忆状态
