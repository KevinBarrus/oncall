## ADDED Requirements

### Requirement: Conservative unified token measurement
系统 SHALL 对聊天历史、记忆摘要输入、Agent 运行时消息和工具输出压缩阈值使用同一 token 计数语义。系统 MUST 优先使用当前 chat model 对应的 tokenizer；当 tokenizer 不可用时，MUST 使用不会低估中文或混合日志内容的保守回退估算。

#### Scenario: Chinese tool output reaches the compression threshold
- **WHEN** 中文或中英混合工具输出按统一计数达到压缩阈值
- **THEN** 系统 MUST 将其视为超阈值输出并执行既有压缩或回退流程

#### Scenario: Model tokenizer is unavailable
- **WHEN** 当前 chat model 没有可用 tokenizer
- **THEN** 系统 MUST 使用保守回退计数完成上下文预算，且不得继续采用可能低估内容的字符除四规则

#### Scenario: Runtime budget uses the same measurement
- **WHEN** Agent 记录工具调用、工具结果或流式模型输出
- **THEN** 运行时预算 MUST 使用与会话上下文相同的 token 计数策略
