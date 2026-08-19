## Why

诊断反馈接口每次请求都会追加人工 SOP evidence。用户重复点击或请求重放会让同一评分被重复计入 3 倍权重，错误改变 Bayesian 后验。

## What Changes

- 为诊断 SOP 反馈引入按 owner、tenant、任务和评分范围去重的持久化幂等键
- 重复提交相同评分时不再追加人工 evidence 或更新后验，并返回已有的 SOP 状态
- 保留同一任务提交不同评分的审计记录，避免将历史反馈与重放请求混淆

## Capabilities

### New Capabilities

- `sop-feedback-idempotency`: 诊断 SOP 人工反馈的幂等持久化、重复提交语义和 owner 隔离

### Modified Capabilities

- 无

## Impact

- 后端：`super_ai.aiops.sop_belief`、诊断反馈路由、SOP belief Repository 和 SQLite 模型
- 数据：新增反馈提交幂等记录及 Alembic migration
- 测试：覆盖同评分重放、不同评分、并发争抢和跨 owner 隔离
