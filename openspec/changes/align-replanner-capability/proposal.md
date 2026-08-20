## Why

Replanner 实际是确定性规则驱动（连续失败次数、证据有无、计划耗尽），不是 LLM 重规划；但 README 与 OpenSpec 主规格表述为"Replanner 决定继续、调整或生成报告"，存在表述落差，可能导致面试与文档夸大当前能力。

## What Changes

- 将 Replanner 能力表述对齐为"规则驱动的受限重规划/回退"，明确不调用 LLM 重新规划计划
- 更新代码注释、README 与 OpenSpec 主规格
- 保留 `autonomous_replan` 契约名（公开 SSE 契约字段），语义澄清为规则触发的知识库回退

## Capabilities

### Modified Capabilities

- `aiops-diagnosis-tasks`: Replanner 决策表述对齐为确定性规则驱动

## Impact

- 诊断代码注释与 SSE 决策消息
- README 与 OpenSpec 主规格
- OpenSpec WIKI 与问题 23 记录
