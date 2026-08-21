## Why

`docs/` 只有本地开发文档，生产环境如何部署（后端托管、Nginx 反代与 SSE、SQLite 备份、监控接入）没有说明。

## What Changes

- 新增 `docs/deployment/production.md`：部署形态总览、uvicorn/systemd 后端、Nginx 反代（SSE 长连接配置）、SQLite WAL 备份与恢复、/health /ready /metrics 监控接入、日志收集、密钥与文件权限、上线检查清单
- operations-and-monitoring.md 与 README 增加入口链接

## Capabilities

纯文档补充，不修改任何代码或行为，`skip_specs: true`。

## Impact

- docs/deployment/production.md（新增）
- operations-and-monitoring.md、README.md 入口链接
