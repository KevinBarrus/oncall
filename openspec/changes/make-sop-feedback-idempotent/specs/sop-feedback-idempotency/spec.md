## Purpose

保证诊断任务的人工 SOP 反馈在重复点击、网络重试和并发重放下只影响一次 Bayesian 后验，同时保留可审计的独立评分记录。

## ADDED Requirements

### Requirement: 相同诊断评分只影响一次后验

系统 SHALL 将同一 owner、tenant、诊断任务和评分视为一个人工 SOP 反馈幂等范围。重复提交该范围内相同评分时，系统 MUST NOT 新增人工 evidence 或再次更新 SOP 后验。

#### Scenario: 重放相同 helpful 评分
- **WHEN** 用户对同一诊断任务再次提交 `helpful`
- **THEN** 接口返回该任务已有的 SOP 后验状态
- **AND** 每个 SOP 的 observations、alpha 和 beta 保持不变

#### Scenario: 并发提交相同评分
- **WHEN** 同一用户并发提交同一诊断任务的相同评分
- **THEN** 系统最多一次写入该评分对应的人工 evidence
- **AND** 后验只接受一次人工评分权重

### Requirement: 不同评分保留独立审计

系统 SHALL 允许同一 owner 对同一诊断任务提交不同评分，并将每种评分作为独立、可审计的人工反馈。

#### Scenario: 提交另一种评分
- **WHEN** 用户已提交 `helpful` 后提交 `not_helpful`
- **THEN** 系统记录新的 `not_helpful` 人工反馈并更新后验一次
- **AND** 原有 `helpful` 反馈记录保持可追溯

### Requirement: 反馈幂等记录遵守 owner 和 tenant 隔离

系统 SHALL 按 owner 和 tenant 隔离人工 SOP 反馈幂等记录及其影响的 SOP evidence。

#### Scenario: 其他用户尝试读取或提交
- **WHEN** 其他 owner 访问不属于自己的诊断任务或其反馈记录
- **THEN** 系统 MUST NOT 暴露该任务的反馈或 SOP 后验
- **AND** 系统 MUST NOT 创建跨 owner 的幂等记录或人工 evidence
