## Why

当前诊断结束时会把所有检索命中的 SOP 都写入成功或失败证据；候选被召回不代表它实际参与了计划或修复，错误反馈会污染 Bayesian 排名并形成自强化偏差。

## What Changes

- 将 SOP belief 更新的归因对象从“全部检索命中”缩小为“被诊断计划实际引用”的 SOP。
- 对所有检索命中保留仅用于审计的曝光信息，不改变其后验。
- 在 SOP evidence 中记录归因阶段和证据强度，区分曝光、计划引用、执行和报告依据。

## Capabilities

### New Capabilities

- `sop-belief-attribution`: SOP 曝光记录、实际使用判定和后验更新归因规则。

### Modified Capabilities

- `aiops-evidence-chain`: 将 SOP 候选曝光和实际归因信息纳入可追溯的诊断证据链。
- `sop-belief-persistence`: 限制可更新 SOP 后验的证据范围，并保存归因元数据。

## Impact

- 后端：`super_ai.aiops.diagnostics`、SOP belief service/repository、SQLite schema 与 Alembic migration。
- 数据：SOP evidence 新增归因阶段和强度；可能新增独立曝光记录。
- 测试：补充候选不更新、计划引用更新、归因字段和跨 owner 隔离回归。
