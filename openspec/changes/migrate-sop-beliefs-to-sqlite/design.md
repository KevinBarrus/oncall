## Context

当前 `SopBeliefRegistry` 将全部 SOP 后验状态和证据保存在进程内，并同步写入 `~/.oncall/sop_beliefs.json`。诊断服务用它对检索命中的 SOP 重排，并在诊断结束或收到人工反馈时更新后验。项目已有异步 SQLAlchemy Repository bundle、SQLite/Alembic 和 owner-scoped 诊断任务；当前单用户模型中，向量检索将 `tenant_id` 设为 `owner_user_id`。

详见 `proposal.md` 与本变更的 delta specs。

## Goals / Non-Goals

**Goals:**

- 用 SQLite 取代 JSON，保留当前 Beta-Bernoulli、人工反馈权重和重排规则。
- 让状态更新和证据写入处于同一事务，并按 owner 与 tenant 作用域查询。
- 保持诊断主链路和反馈 API 的调用语义，仅把同步 Registry 改为异步服务。

**Non-Goals:**

- 不自动导入旧 JSON，不修改历史文件。
- 不在本变更中调整 SOP 成功归因或人工反馈幂等性；它们由问题 12、13 处理。
- 不引入多租户身份体系；当前 tenant 值继续从认证用户的 `id` 推导。

## Decisions

### 1. 新增两个 SQLite 表，而不复用通用诊断 evidence 表

新增 `sop_belief_states` 与 `sop_belief_evidence`。前者按 `(owner_user_id, tenant_id, document_id, document_version)` 唯一保存 alpha、beta、失败模式/上下文聚合值、均值、观测数和更新时间；后者逐条保存任务、结果、来源、失败模式、使用指标、元数据和创建时间。

`document_version` 使用知识文档的 `content_hash`，它已随文档内容变化而改变，适合区分同一 document ID 的不同内容版本。诊断通用 evidence 仍保存运行证据；SOP evidence 是后验更新的领域审计记录，避免把聚合状态和通用运行日志混在一个可变 JSON payload 中。

备选方案是只在 `DiagnosticEvidenceModel.payload` 中加入 belief 字段；这会使状态查询依赖全表聚合，无法为不同文档版本建立唯一约束，也不能原子地维护后验。

### 2. 在 Repository 中以单事务写证据并更新后验

增加 `SopBeliefRepository` Protocol、记录类型和 SQLite 实现，并挂到 `MemoryRepositories`。其 `record()` 接口接收已由认证上下文推导的 owner/tenant 以及完整证据，在一个 session transaction 中：插入 evidence，使用 SQLite `INSERT ... ON CONFLICT DO UPDATE` 更新对应 state 的计数、均值和 JSON 聚合字段，然后提交。

这样多个进程不会再覆盖同一个内存快照；唯一索引和数据库写事务保证每次 evidence 都对应一次后验更新。备选方案是应用级锁；它无法覆盖多进程，也不能提供持久化原子性。

### 3. 领域规则保留在 `sop_belief.py`，存储替换为异步服务

保留 `DiagnosticEvidence`、`SopBeliefState` 和 `decide_rewrite()` 作为不依赖存储的领域值对象。用小型 `SopBeliefService` 替代 JSON Registry：它将 Repository record 转为领域状态，并提供 `record`、`record_feedback`、`top_sops` 等异步操作。诊断服务和反馈路由改为 await 该服务；应用装配时从 `MemoryRepositories` 构造它。

备选方案是让诊断服务直接调用 Repository；这会把贝叶斯规则、反馈派生和存储映射分散到调用方，增加后续归因修复的范围。

### 4. 当前 tenant 采用显式列，但值由 owner 推导

虽然当前认证记录只包含用户 ID，SOP 表仍保存 `tenant_id`，并在调用处固定传入 `owner_user_id`，与现有 Milvus scope 一致。Repository 每个查询同时过滤两者，不接受 API 请求体提供的 tenant。未来接入组织租户时，只替换认证上下文的 tenant 解析，不改变表主键和查询边界。

### 5. 重排按检索结果逐个批量读取状态

`top_sops` 改为一次按 document IDs 查询当前 scope 的 belief state，再在内存中套用现有组合分数和稳定排序规则。避免每个 SOP 一次数据库查询；不增加缓存，因为诊断每次最多处理少量命中，且实时状态比缓存命中更重要。

## Risks / Trade-offs

- [SQLite 写入竞争导致短暂 `database is locked`] → 沿用现有 session/SQLite 配置，并让 Repository 只执行短事务；错误仍不能中断诊断主流程。
- [文档内容改变后旧版本状态不参与新版本重排] → 这是防止旧 SOP 证据污染新内容的预期行为；旧版本记录保留用于审计。
- [本地 JSON 旧数据不会显示] → 本变更明确不自动迁移；需要时可在离线维护工具中显式导入。
- [诊断更新失败造成排序没有新证据] → 记录安全日志并继续返回诊断结果；不得伪造已持久化状态。

## Migration Plan

1. 新增 ORM models、Repository contract/implementation 和 Alembic revision，创建两张表及 owner/tenant/document/task 查询索引。
2. 将应用依赖装配、诊断重排/证据记录与反馈路由改为异步 SOP belief service。
3. 删除 JSON 文件读写逻辑和应用状态中的 JSON registry；保留纯领域计算对象。
4. 运行迁移与 Repository、owner 隔离、事务更新、诊断重排回归测试。
5. 回滚时执行 Alembic downgrade 并部署前一版应用；旧 JSON 不受本变更影响，但 SQLite belief 数据在 downgrade 后不再可用。
