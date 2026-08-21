## Context

solution3.md 问题28：无覆盖率报告与阈值。方案：CI 增加 `pytest --cov`，全局最低阈值（如 70%），关键模块要求更高。

## Goals / Non-Goals

**Goals:**

- CI 输出覆盖率报告并设全局阈值（低于则失败）
- 关键模块（auth/chat/aiops）阈值高于普通模块

**Non-Goals:**

- 不按单文件设阈值（coverage.py 不支持 per-file fail_under；单文件波动大）
- 不强制前端覆盖率（Vue 组件测试已有 82 个，前端门禁保持 typecheck/test/build）

## Decisions

- 全局 `fail_under = 80`（基线 87%，保留波动余量）
- 关键域按**目录聚合**阈值：auth 80%、chat 75%、aiops 75%（基线 94/81/83%）
- `scripts/check_coverage.py` 读 coverage.json 按 `super_ai/<domain>` 前缀聚合行覆盖率
- CI：pytest 步骤带 `--cov --cov-report=json --cov-fail-under=80`，随后跑域检查脚本

## Risks / Trade-offs

- [覆盖率收集增加 CI 耗时] → 一次运行同时完成回归与门禁，约 +30s
- [域聚合掩盖单文件低覆盖] → llm/rerank 47% 被全局拉平；域阈值已按"关键域"收窄，其余模块由全局 80% 约束

## Migration Plan

无 schema 变更。
