## Why

CI 后端 job 对同一测试套件跑两遍（裸 pytest + 带 --cov 重跑），浪费约一半时间；运维端点（/health、/ready、/metrics、/config/check、/health/mcp）无认证且返回基础设施拓扑/指标，部署文档未明确公网暴露边界。

## What Changes

- CI 合并为一次带 `--cov` 的运行（回归 + 覆盖率门禁同一次执行）
- 部署文档补运维端点安全边界（不对外暴露 / Nginx 限制来源 IP）+ 检查清单项

## Capabilities

CI 合并 + 部署安全边界文档，`skip_specs: true`。

## Impact

- .github/workflows/ci.yml
- docs/deployment/production.md
