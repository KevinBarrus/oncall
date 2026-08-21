## Context

solution3.md 问题5：跨轮证据按 4000 字符直接截断且未去重。方案：按 ID 去重 + token-aware 整条丢弃式截断。

## Goals / Non-Goals

**Goals:**

- 重复证据（同工具同摘要、同引用）只注入一次
- 超预算时丢弃整条而非截半，避免破坏结构

**Non-Goals:**

- 不引入精确 tokenizer（跨轮上下文用字符预算近似即可，现有 4000 字符限制不变）
- 不按相关性排序历史证据（方案建议项，成本高收益低，留待未来）

## Decisions

- 去重键：审计行 `(tool_name, result_summary)`（不同调用 ID 但内容相同视为重复）；citation 行按 `id`
- 预算：`_append_line` 逐行检查 `used + len(line) + 1 > limit`，超限跳过该条（continue），不提前终止
- 移除 `content[:4000]` 整体截断

## Risks / Trade-offs

- [行级字符估算非精确 token] → 与既有 `_CROSS_TURN_CONTEXT_LIMIT`（字符）一致，预算语义未变
- [同 tool 不同调用被去重] → 相同摘要视为无新增信息，符合"浪费预算"的修正目标

## Migration Plan

无 schema 变更。
