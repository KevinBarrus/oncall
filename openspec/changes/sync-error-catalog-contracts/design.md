## Context

solution3.md 问题13：错误码双份手动同步易漏改。方案：error_catalog.py 作 single source of truth 自动生成 errors.ts，或契约测试断言两端一致。

## Goals / Non-Goals

**Goals:**

- 新增/修改错误码时，两端不一致能被 CI 或契约测试拦截
- 生成 JSON 为确定性输出（排序 + 固定字段）

**Non-Goals:**

- 不把 errors.ts 完全替换为自动生成（TS 类型/枚举仍手写，JSON 仅作一致性依据）
- 不引入 pre-commit hook（CI 校验已足够）

## Decisions

- `sync_error_catalog.py`：读 `ERROR_DEFINITIONS`（三元组）输出 `{code: {category, httpStatus, message}}` 到 `src/generated/error-catalog.json`（提交）
- 契约测试 `loadBackendErrorCatalog` 用 Node fs 读 JSON（tsconfig 未开 resolveJsonModule），双向断言：
  - `Object.keys(API_ERROR_CODES)` 与 JSON keys 完全相等（排序后）
  - 每个码的 category/httpStatus/message 逐字段一致
- CI backend job 加 "Error catalog sync check"：`uv run python scripts/sync_error_catalog.py && git diff --exit-code`

## Risks / Trade-offs

- [生成 JSON 提交进 src/] → 被 tsc 忽略（非 .ts），vitest 用 fs 读取，无类型影响
- [CI 需 git 上下文] → checkout 已提供；路径用相对 CWD（apps/backend → ../../packages/...）

## Migration Plan

无 schema 变更。
