# 服务拓扑与依赖关系

> 基于 2026-07 架构快照 | 架构组维护

---

## 整体架构

```
                          ┌─────────────────┐
                          │   CDN / WAF     │
                          └────────┬────────┘
                                   │
                          ┌────────▼────────┐
                          │   api-gateway   │  ← P0 核心入口
                          │   (Kong 3.x)    │
                          └──┬──┬──┬──┬─────┘
                             │  │  │  │
              ┌──────────────┘  │  │  └──────────────┐
              │                 │  │                  │
    ┌─────────▼──────┐  ┌──────▼──▼───────┐  ┌───────▼──────────┐
    │  user-service  │  │  order-service  │  │  notification-   │
    │  (Go 1.22)     │  │  (Java 21)      │  │  service (Python) │
    └────────┬───────┘  └──────┬──────────┘  └───────┬──────────┘
             │                 │                      │
    ┌────────▼───────┐  ┌──────▼──────────┐  ┌───────▼──────────┐
    │   user-db      │  │  order-db       │  │  message-queue   │
    │   (MySQL 8.0)  │  │  (MySQL 8.0)   │  │  (RabbitMQ 3.12) │
    └────────────────┘  └─────────────────┘  └──────────────────┘
```

## 服务清单

| 服务名 | 语言/框架 | 端口 | 部署方式 | 副本数 | 关键依赖 |
|--------|----------|------|----------|--------|---------|
| api-gateway | Kong 3.6 | 8443 (HTTPS) | K8s Deployment | 3 | 下游 3 个 service |
| user-service | Go 1.22 / Gin | 8080 | K8s Deployment | 3 | user-db, Redis |
| order-service | Java 21 / Spring Boot 3 | 8081 | K8s Deployment | 2 | order-db, user-service (gRPC), Redis |
| notification-service | Python 3.12 / FastAPI | 8082 | K8s Deployment | 2 | RabbitMQ, user-service |

## 数据层

| 实例 | 类型 | 版本 | 连接池上限 | 备份策略 |
|------|------|------|-----------|---------|
| user-db | MySQL | 8.0.35 | max_connections=400 | 每日全量 + binlog 增量 |
| order-db | MySQL | 8.0.35 | max_connections=300 | 每日全量 + binlog 增量 |
| redis-cache | Redis | 7.2.4 | maxclients=10000 | AOF everysec, RDB 每小时 |
| message-queue | RabbitMQ | 3.12.10 | — | 每日定义导出 |

## 依赖路径（影响面分析）

### 读路径
- `用户信息查询`: api-gateway → user-service → user-db + Redis
- `订单查询`: api-gateway → order-service → order-db + Redis
- `消息推送`: api-gateway → notification-service → RabbitMQ → user-service (查用户 channel)

### 写路径
- `用户注册`: api-gateway → user-service → user-db（同步写）+ Redis（异步更新）
- `下单`: api-gateway → order-service → order-db + user-service（gRPC 校验用户状态）+ RabbitMQ（发订单事件）

## 已知脆弱点

1. **order-service 对 user-service 的 gRPC 调用无降级** — user-service 抖动会导致下单失败
2. **Redis 单实例** — 挂了影响 user/order 两个服务的缓存命中率，DB 会被打爆
3. **log-aggregator 是单点** — 但属于 Support Tier，允许工作日修复
4. **RabbitMQ 无镜像队列** — 节点重启会丢消息
