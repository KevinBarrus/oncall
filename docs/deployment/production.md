# 生产部署指南

> **状态说明**：本项目是本地优先工具——`infra/compose.yaml` 只托管基础设施（etcd、MinIO、Milvus、Attu、Alertmanager），后端、前端与 CLS MCP Server 默认在本机以进程方式运行。本文给出将当前架构部署到生产环境（单机 Linux 服务器）的**建议与示例配置**，标注「建议」的部分需按你的环境调整；**不要提交** `config/project.json` 与 `config/user.project.json`。

## 部署形态总览

| 组件 | 生产运行方式 | 说明 |
| --- | --- | --- |
| 基础设施 | Docker Compose（`infra/compose.yaml`） | etcd、MinIO、Milvus、Attu、Alertmanager，数据目录已挂载持久卷 |
| 后端 | `uvicorn` + systemd | FastAPI 应用 `super_ai.api.app:create_app` |
| 前端 | 静态构建产物 + Nginx | `npm run frontend:build` 产物由 Nginx 托管并反代后端 |
| CLS MCP | 官方 `cls-mcp-server` CLI 进程 | 配置来源为 `config/*.json` 的 `clsMcpServer` 段 |

**推荐单 worker 运行后端**：SQLite 是文件数据库（`apps/backend/var/memory.sqlite3`），后台任务租约与 per-kind 并发限制是进程内语义；多 uvicorn worker 会引入跨进程写竞争，当前架构按单进程设计。

## 1. 基础设施（容器）

```bash
# 拉起基础设施（与本地一致）
docker compose -f infra/compose.yaml up -d etcd minio milvus attu alertmanager
```

生产环境建议：为 `etcd-data`、`minio-data`、`milvus-data`、`alertmanager-data` 卷配置定期快照；Milvus 建议按官方文档调大内存与磁盘配额。

## 2. 后端（uvicorn + systemd）

先准备依赖并执行迁移：

```bash
cd apps/backend
uv sync
uv run alembic upgrade head
```

`/etc/systemd/system/oncall-backend.service` 示例：

```ini
[Unit]
Description=Oncall Agent backend
After=docker.service network-online.target
Requires=docker.service

[Service]
User=oncall
WorkingDirectory=/opt/oncall/apps/backend
ExecStart=/opt/oncall/.local/bin/uv run uvicorn super_ai.api.app:create_app --factory --host 127.0.0.1 --port 8000
Restart=on-failure
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

注意：项目配置**只从** `config/project.json` 与 `config/user.project.json` 读取，不要通过 systemd `Environment=` 注入项目配置。

启动：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now oncall-backend
```

## 3. 前端构建与 Nginx 托管

```bash
npm install
npm run frontend:build   # 产物输出到 apps/frontend/dist
```

将 `apps/frontend/dist` 部署到服务器（示例 `/opt/oncall/frontend-dist`），Nginx 站点配置见下节。

## 4. Nginx 反代与 SSE 要点

SSE 是长连接流，代理必须关闭缓冲、拉长读超时，否则流会被代理缓冲截断或提前断开。

`/etc/nginx/sites-available/oncall` 示例：

```nginx
server {
    listen 80;
    server_name oncall.example.com;

    # 前端静态资源
    root /opt/oncall/frontend-dist;
    index index.html;
    location / {
        try_files $uri $uri/ /index.html;
    }

    # 后端 API 与 SSE（按现有路由前缀反代）
    location ~ ^/(auth|chat|aiops|knowledge|documents|mcp|feedback|prompts|skills|health|ready|metrics|config|openapi) {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE 长连接关键配置
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }
}
```

检查并重载：

```bash
sudo nginx -t && sudo systemctl reload nginx
```

## 5. SQLite 备份与恢复

数据库文件：`apps/backend/var/memory.sqlite3`（WAL 模式）。

**在线备份**（推荐，避免直接复制主库文件）：

```bash
cd apps/backend
uv run python -c "import sqlite3; sqlite3.connect('var/memory.sqlite3').execute('PRAGMA wal_checkpoint(TRUNCATE)')"
sqlite3 var/memory.sqlite3 ".backup '/backup/oncall-$(date +%F).sqlite3'"
```

或使用 SQLAlchemy 官方备份示例脚本。**不要**在运行中直接 `cp` 主库文件（WAL 未合并时会丢最近写入）。

恢复：停止后端，将备份文件放回 `apps/backend/var/memory.sqlite3`（连同 `-wal`/`-shm` 一并删除后由 SQLite 重建），再启动并执行 `uv run alembic upgrade head` 校验 schema。

建议：每日备份 + 保留 N 份轮转；Milvus 向量库由上传文档与索引任务重建（`var/` 之外无需额外备份）。

## 6. 监控与告警

后端已暴露：

- `GET /health`——存活检查
- `GET /ready`——就绪检查（SQLite、Milvus、Qwen 与 MCP）
- `GET /metrics`——本地请求指标（requestCount / failureCount / averageLatencyMs）
- `GET /config/check`——配置校验

接入方式建议：

- 探活：systemd/Nginx 健康检查指向 `/health` 与 `/ready`
- 指标采集：将 `/metrics` 接入 Prometheus（`scrape_interval` 建议 ≥ 15s）
- 告警：项目自带 Alertmanager（`infra/compose.yaml`），可用于本地 active-alert 演示；生产告警源按你的监控栈配置

## 7. 日志收集

- 后端结构化日志输出到 stdout（super_ai 命名空间，已对敏感键值脱敏），进程日志同时写入 `apps/backend/var/`
- 收集建议：systemd journal 或日志代理（如 Loki/Promtail）采集 stdout；`var/` 下按日轮转
- 不要将含真实凭据的 config 内容写入日志——脱敏由 `observability.py` 的 `SanitizingFormatter` 与 `emit_event` 双重保证

## 8. 密钥与文件权限

- 配置只保存在 `config/project.json` / `config/user.project.json`（Git 忽略），生产环境建议：

```bash
chmod 600 config/project.json config/user.project.json
```

- 数据库文件同样建议限制权限（含密码哈希与聊天历史）：

```bash
chmod 600 apps/backend/var/memory.sqlite3
```

- 模板中的凭据字段保持为空；密钥泄露时在对应云平台立即轮换

## 9. 上线检查清单

- [ ] `config/project.json` / `config/user.project.json` 已配置且未提交
- [ ] `uv run alembic upgrade head` 执行成功
- [ ] 基础设施容器健康（`docker compose -f infra/compose.yaml ps`）
- [ ] `curl http://127.0.0.1:8000/ready` 返回就绪
- [ ] Nginx SSE 路径未开 `proxy_buffering`，`proxy_read_timeout` ≥ 3600s
- [ ] SQLite 备份任务已配置并验证恢复
- [ ] `/metrics` 可被监控栈抓取
- [ ] 系统防火墙仅暴露 80/443 与必要端口
