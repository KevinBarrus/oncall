## Purpose

将 SOP 候选曝光与实际诊断归因分离，确保 Bayesian 后验只反映真正参与诊断决策的 SOP，避免检索噪声污染后续排序。

## ADDED Requirements

### Requirement: 候选曝光不更新 SOP 后验

系统 SHALL 为检索到的 SOP 候选保留可审计的曝光信息，但候选仅因被检索到时 MUST NOT 创建会改变 SOP 后验状态的 evidence。

#### Scenario: SOP 仅作为候选出现
- **WHEN** Planner 检索到 SOP，但生成的诊断计划未引用该 SOP
- **THEN** 系统保留该 SOP 的曝光记录
- **AND** 该 SOP 的 alpha、beta 和 observations 不发生变化

### Requirement: 只有实际引用的 SOP 可以更新后验

系统 SHALL 仅为诊断计划实际引用的 SOP 创建可更新后验的结果 evidence。

#### Scenario: 计划引用一个 SOP
- **WHEN** Planner 生成的诊断计划明确引用一个 SOP
- **THEN** 诊断完成后系统为该 SOP 写入结果 evidence 并更新后验
- **AND** 同批未被计划引用的 SOP 不更新后验

### Requirement: 归因信息可追溯

系统 SHALL 为每条 SOP 曝光或结果 evidence 保存归因阶段和证据强度，以区分候选、计划引用、执行和报告依据。

#### Scenario: 查询 SOP 结果 evidence
- **WHEN** 授权调用者查询某个 SOP 的诊断证据
- **THEN** 每条记录包含归因阶段和证据强度
- **AND** 调用者可以区分曝光记录与后验更新记录
