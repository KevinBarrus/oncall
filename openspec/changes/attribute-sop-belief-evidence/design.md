## Context

Planner 当前把 SOP 命中内容交给模型，但 plan step 没有稳定的 SOP 引用字段；诊断结束时因此只能将全部 `sop_hits` 当作已使用 SOP。详见 `proposal.md`。

## Goals / Non-Goals

**Goals:**

- 让计划显式声明它引用的 SOP document IDs。
- 将候选曝光与可更新后验的结果 evidence 分开保存。
- 让结果 evidence 保留归因阶段和强度，供审计和后续排序解释。

**Non-Goals:**

- 不从自然语言 purpose 或报告文本猜测 SOP 引用。
- 不在本变更中修改人工反馈的幂等规则。
- 不将“执行成功”误认为某个 SOP 必然导致成功；本轮只记录计划引用这一事实。

## Decisions

### 1. 为计划增加可校验的 `sopDocumentIds`

Planner prompt 要求模型返回与 plan 并列的 `sopDocumentIds`。验证器仅保留本次检索结果中的 document ID；缺失、无效或 generic plan 时为空列表。诊断完成后只对该列表写入结果 evidence。

不从 step purpose、引用内容或报告文本做字符串匹配：这些文本不稳定，会再次把候选误判为实际使用。

### 2. 曝光写入独立的不可更新审计记录

为每个候选 SOP 写入 exposure record，保存 document/version、任务、owner/tenant、阶段 `retrieval` 和强度 `candidate`。该记录不关联或更新 `sop_belief_states`。

复用可更新的 SOP evidence 表会迫使后验更新逻辑为每条记录分支，也会让“evidence”一词难以区分是否影响后验；独立曝光记录的查询语义更清晰。

### 3. 结果 evidence 记录归因元数据

SOP belief evidence 新增 `attribution_stage` 和 `evidence_strength`。本轮自动记录使用 `plan` / `planned`；未来执行或报告直接引用时可使用更高强度，不需要变更主键或查询边界。

### 4. 反馈仅基于已归因结果 evidence

人工反馈继续按 task 查询 SOP evidence，因此 exposure 不会成为人工反馈的候选；这避免反馈再次把未使用 SOP 带入后验。

## Risks / Trade-offs

- [模型漏填 `sopDocumentIds`] → 采用保守策略：不更新后验，曝光仍可审计。
- [模型填入错误 ID] → 验证器与本次检索 document ID 取交集。
- [新增审计表增加存储] → 每次诊断只记录有限 top-k 候选，且保留价值高于体积成本。

## Migration Plan

1. 增加曝光表和结果 evidence 的归因字段，使用 Alembic migration。
2. 扩展计划契约、验证器与诊断状态，持久化候选曝光。
3. 在 report 节点仅根据已验证的 `sopDocumentIds` 写入可更新 evidence。
4. 补充候选、计划引用、反馈和 owner 隔离测试；升级后旧 evidence 保持兼容默认归因值。
