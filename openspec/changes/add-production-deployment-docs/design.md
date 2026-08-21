## Context

solution3.md 问题26：缺生产部署文档。方案要求覆盖 Docker Compose 生产模式、Nginx 反代（SSE `proxy_read_timeout`）、SQLite 备份、监控告警、日志收集。

## Goals / Non-Goals

**Goals:**

- 给出与当前架构一致的生产部署建议（基础设施容器 + uvicorn/systemd + Nginx 前端）
- SSE 长连接代理要点明确（关缓冲、拉长读超时）

**Non-Goals:**

- 不新增 Dockerfile / 应用编排（现状为本地优先，文档只给建议，不虚构已支持能力）
- 不改动任何代码

## Decisions

- 明确标注文档为「建议与示例配置」，与本地优先现状一致
- 后端建议单 worker（SQLite 文件数据库 + 进程内后台任务语义）
- 备份采用 WAL checkpoint + `sqlite3 .backup` 在线方式，并说明直接 cp 主库的风险
- 监控复用现有 `/health` `/ready` `/metrics` `/config/check` 端点
- 密钥/数据库文件权限建议 0600（呼应问题12 的 P2 项）

## Risks / Trade-offs

- [示例配置未经实际生产验证] → 文档标注为建议，按环境调整；给出上线检查清单便于验证

## Migration Plan

无 schema 变更。
