## Why

前端 `errors.ts` 与后端 `error_catalog.py` 双份手动同步同一套错误码，新增/修改错误码容易漏改一端，且现有契约测试只测形状不测跨端一致性。

## What Changes

- 后端 `error_catalog.py` 作为单一事实来源，新增 `apps/backend/scripts/sync_error_catalog.py` 生成共享 `packages/api-contracts/src/generated/error-catalog.json`
- 契约测试新增双向一致性断言（前端码 ⊆ 后端码 且字段一致；后端码 ⊆ 前端码）
- CI 后端 job 增加生成校验（重新生成后 `git diff --exit-code`）

## Capabilities

纯契约治理工具链，不修改任何运行时行为，`skip_specs: true`。

## Impact

- 生成脚本 + 提交的 error-catalog.json
- 契约测试与 ci.yml
