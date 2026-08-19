## MODIFIED Requirements

### Requirement: Tool output compression fallback is observable

系统 SHALL 在大工具输出无法生成 LLM 摘要时使用既有采样回退，并 MUST 发出不含原始工具输出或异常正文的结构化降级事件。

#### Scenario: Tool summary generation fails
- **WHEN** 大工具输出的摘要模型调用失败或返回空摘要
- **THEN** 系统 MUST 返回采样压缩结果，并记录工具名、`sampled_fallback` 模式和安全失败类别。
