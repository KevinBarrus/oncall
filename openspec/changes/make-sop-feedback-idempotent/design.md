## Context

诊断反馈路由在每次请求中调用 `record_feedback()`；该方法会为任务中的每个 SOP 追加 manual evidence。现有 evidence 表没有表示“该评分已经提交”的唯一键，因此单靠查询后跳过无法抵御并发请求。

## Goals / Non-Goals

**Goals:**

- 以数据库唯一约束作为同评分反馈的并发裁决点
- 将幂等声明与所有人工 evidence、posterior 更新置于同一事务
- 重放时返回当前相关 SOP 状态而不修改数据

**Non-Goals:**

- 不合并 `helpful` 与 `not_helpful` 为可变的单一反馈
- 不修正上线前已经被重复计入的历史 posterior
- 不改变通用 `/feedback` 的 upsert 语义

## Decisions

### 1. 使用独立的 feedback submission 表

新增 owner、tenant、task 和 rating 组成的唯一约束的 submission 表，而不是在 JSON metadata 中查找人工 evidence。该表清楚表达一次用户评分，且可以让数据库拒绝并发重放。

复用 `sop_belief_evidence` 的替代方案会让每个 SOP 都承担一次提交标记，无法原子地表示“一个评分影响多个 SOP”。

### 2. Repository 以一个事务完成 claim 和 evidence 更新

新增一个 SOP belief Repository 操作：先通过 SQLite `INSERT OR IGNORE` 创建 submission，再在同一事务内读取该任务的 auto evidence、去重 SOP 文档版本、追加 manual evidence 并更新 state。未获得 claim 时仅读取这些 SOP 的当前 state 并返回，不再写入。

服务层继续负责将 `helpful`/`not_helpful` 转为结果与告警上下文；Repository 负责 SQLite 事务和 scope。这样不会出现“先声明已提交、后写 evidence 失败，重试却被永久跳过”的半完成状态。

### 3. 只以自动结果 evidence 作为人工反馈目标

新反馈从当前任务的 `source=auto` evidence 提取 SOP 文档版本，不将之前的 manual evidence 当作新的目标来源。这样不同评分各影响同一组计划归因 SOP 一次，不会随着反馈次数扩大目标集合。

## Risks / Trade-offs

- [旧数据没有 submission] → 新约束从升级后生效，历史重复证据保留审计且不自动重算 posterior
- [SQLite 并发写入竞争] → 唯一约束和单事务保证最多一个请求获得 claim，调用方可重试数据库 busy 错误
- [同任务没有 auto evidence] → 仍记录 submission，返回空 SOP 状态，避免后续重放在任务结果变化后产生不一致写入

## Migration Plan

1. 通过 Alembic 创建 submission 表及唯一约束
2. 部署 Repository、服务和路由调用改造
3. 用重复、不同评分、并发和跨 owner 测试验证行为
4. 回滚时保留 submission 审计数据；旧应用忽略该表
