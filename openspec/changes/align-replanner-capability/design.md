## Context

`_determine_contract` 是 4 条确定性规则（计划耗尽 / 连续失败 ≥2 / 失败且零证据 / 否则），不调用 LLM；`autonomous_replan` 也只是在 Executor 中强制回退到知识库检索。方案要求把能力表述为"规则驱动的受限重规划/回退"，保留 AIOps 可预测性，不引入 LLM 重规划。

## Goals / Non-Goals

**Goals:**

- 文档与代码表述与实际能力一致（规则驱动）
- 保留公开 SSE 契约字段（`contract` 值不变）以兼容前端与测试
- 明确不引入 LLM 重规划，除非案例证明规则无法覆盖

**Non-Goals:**

- 不改造 Replanner 为 LLM 重规划（方案明确暂不引入）
- 不改动 `contract` 字段值（公开契约）

## Decisions

- `_determine_contract` docstring 重写：明确"确定性规则，不调用 LLM"，`autonomous_replan` 语义澄清为规则触发的 KB 回退
- Replanner SSE 决策消息改为 "rule-triggered KB fallback (no LLM replan)"
- README 与 OpenSpec 主规格同步表述，并新增 Scenario 明确规则驱动
- change delta 用 MODIFIED Requirements（包含原 requirement 全部 scenario）

## Risks / Trade-offs

- [contract 名 autonomous_replan 仍有歧义] → 保留公开契约字段，用注释与文档澄清语义；改名需同步前端与测试，风险大于收益

## Migration Plan

无 schema 变更。仅表述对齐，行为与 SSE 契约不变。
