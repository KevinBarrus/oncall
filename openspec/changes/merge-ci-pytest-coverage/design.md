## Context

solution4.md 问题15（P2，确认项）：`ci.yml:48-53` 同一套件跑两遍；运维端点无认证（单实例 127.0.0.1 下风险低，部署文档指导 Nginx 对外时需明确边界）。

## Goals / Non-Goals

**Goals:**

- CI 一次运行完成回归 + 覆盖率门禁
- 部署文档明确运维端点公网边界

**Non-Goals:**

- 不给运维端点加认证（监控/探活需要无凭据访问；单实例本地绑定风险低，属部署边界而非代码缺陷）
- 不重构 Nginx 配置模板（文档说明为建议）

## Decisions

- CI：`Pytest (offline regression)` 与 `Coverage (regression + thresholds)` 合并为单一步骤（`pytest --cov ... --cov-fail-under=80` + `check_coverage.py`）
- 部署文档：监控节加"运维端点不要求认证、不直接暴露公网"边界说明；上线检查清单补对应项

## Risks / Trade-offs

- [合并后回归失败定位略粗] → 覆盖率步骤仍输出 term 报告，失败信息一致

## Migration Plan

无。
