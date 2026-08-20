## Context

`authorization-and-tenant-isolation` spec 已写明"user ID 用作 tenant 范围，直到引入单独的组织 tenant 模型"。剩余工作是把这一模型在代码注释与 README 中显式化，避免"预留复杂度但表述不清"。

## Goals / Non-Goals

**Goals:**

- 明确"单用户即单租户"模型，tenant 范围等于 owner 用户
- 保持现有 owner scope 隔离行为不变

**Non-Goals:**

- 不引入独立 tenant/成员模型（方案明确暂不设计）
- 不改动 `tenant_id=owner_user_id` 的传参行为（这正是当前模型的实现）

## Decisions

- `SopBeliefService` 类注释补充租户模型说明
- README"用户与 tenant 隔离"条目明确"单用户即单租户"
- OpenSpec 主规格已覆盖（不重复修改）

## Risks / Trade-offs

- [多租户字段仍预留] → 作为未来组织级隔离的扩展点，当前 owner scope 隔离不变

## Migration Plan

无 schema 变更。纯说明性同步。
