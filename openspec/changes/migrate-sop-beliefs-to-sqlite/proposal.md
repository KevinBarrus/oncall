## Why

当前 SOP belief 和诊断证据写入用户目录下的单一 JSON 文件，绕过了项目既有的 owner/tenant 隔离、事务、迁移、审计与备份边界；多进程写入还可能损坏状态。随着 belief 已参与 AIOps SOP 排序，这些问题会直接影响不同用户的诊断结果。

## What Changes

- 将 SOP belief state 和 SOP evidence 从本地 JSON 迁移到 SQLite，并由 Alembic 管理 schema。
- 为 belief 与 evidence 引入 owner、tenant、document、document version、diagnostic task 作用域，所有读写通过 Repository 执行。
- 将诊断和人工反馈调用改为异步持久化边界，保留现有 Beta-Bernoulli 更新与排序行为。
- **BREAKING**：移除 `~/.oncall/sop_beliefs.json` 作为运行时存储；本地旧 JSON 不自动导入。

## Capabilities

### New Capabilities

- `sop-belief-persistence`: 持久化、隔离和查询 SOP belief 及其诊断证据。

### Modified Capabilities

- `memory-repositories`: 将 SOP belief/evidence 纳入 SQLite schema、Alembic 迁移与 Repository 边界。
- `authorization-and-tenant-isolation`: 将 SOP belief/evidence 纳入 user-owned 数据隔离范围。

## Impact

- 后端：`super_ai.aiops.sop_belief`、诊断服务、反馈 API、应用依赖装配、memory models/repositories/sqlite。
- 数据：新增 SQLite 表和 Alembic revision；不再读写用户目录 JSON。
- 测试：补充迁移、owner 隔离、证据持久化和诊断排序回归测试。
