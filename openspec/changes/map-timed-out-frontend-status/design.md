## Context

solution4.md 问题5（P2，回归：solution3 问题7 配套）：契约 `sse.ts:71` 已含 `timed_out`，后端 `aiops/diagnostics.py:283-288` 序列完整；前端 `asyncStatus.ts` STATUS_DESCRIPTIONS 无该条目，`describeAsyncStatus` 回退 `UNKNOWN_STATUS`。

## Goals / Non-Goals

**Goals:**

- 超时诊断历史显示准确标签（"诊断超时"，danger 色调）

**Non-Goals:**

- 不改变契约/后端 SSE（已正确）
- 不新增其他状态映射

## Decisions

- 映射 `timed_out: { label: "诊断超时", tone: "danger", active: false }`（与 degraded/failed 同色调语义；active=false 表示终态）
- 在既有 `chineseWorkspace.test.ts` 状态断言块补一行（该文件是状态映射的中文文案测试）

## Risks / Trade-offs

- [label 文案"诊断超时"仅覆盖 AIOps 场景] → timed_out 目前仅由诊断任务使用，契约内其他使用者后续再扩展

## Migration Plan

无。
