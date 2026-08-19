## ADDED Requirements

### Requirement: SOP 后验只接受已归因证据

系统 SHALL 只使用归因阶段为计划引用、执行或报告依据的 SOP evidence 更新后验状态；候选曝光 evidence MUST NOT 改变后验。

#### Scenario: 曝光 evidence 被持久化
- **WHEN** 系统保存一个 SOP 候选曝光 evidence
- **THEN** 系统保存其审计字段
- **AND** 不创建或更新对应的 SOP 后验状态
