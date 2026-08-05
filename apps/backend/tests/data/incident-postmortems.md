# 历史故障复盘记录

> 内部知识沉淀 | 遵循 Blameless 复盘原则 | 仅记录已结案故障

---

## INC-2026-0715: api-gateway 504 大面积超时

**发生时间**: 2026-07-15 14:22-15:08（持续 46 分钟）
**等级**: P0-Critical
**影响**: 全部用户无法访问，影响约 12 万 UV
**值班人**: zhang-san (主), li-si (副)

### 时间线

| 时间 | 事件 |
|------|------|
| 14:22 | api-gateway P99 延迟从 200ms 飙升到 3500ms，Prometheus 触发 P0 告警 |
| 14:25 | zhang-san 确认告警，开始排查 |
| 14:32 | 发现 user-service 3 个 Pod 中 2 个处于 CrashLoopBackOff |
| 14:35 | 查看 user-service 日志，报 `too many connections` (MySQL) |
| 14:40 | 查看 user-db，发现连接数已达到 max_connections=400 上限 |
| 14:42 | 临时调大 max_connections 到 600，user-service 恢复 |
| 14:50 | 发现根因：order-service 在 14:15 发布了一个版本，gRPC 连接池配置错误（poolSize 从 20 改成 200），导致对 user-db 的间接连接暴涨 |
| 14:55 | 回滚 order-service 到上一版本 |
| 15:08 | 全部服务恢复正常 |

### 根因

order-service 发布变更中，gRPC 连接池 poolSize 参数被误改为 200（正常值 20），导致通过 order-service → user-service → user-db 的调用链产生了 10 倍的数据库连接，user-db 连接池耗尽，user-service 无法查询 DB 而 CrashLoop。

### Action Items

- [x] order-service gRPC 连接池配置加入 code review checklist ✅ 2026-07-18
- [x] user-db 连接数增加 Grafana 面板，阈值告警设为 70% ✅ 2026-07-20
- [ ] 在 order-service 和 user-service 之间加 circuit breaker —— **已排期 8 月迭代**
- [ ] 配置 max_connections 的自动扩容策略 —— **评审中**

### 经验教训

**调用链放大效应**: 上游的一个小配置变更，经过"服务 A → 服务 B → DB"的调用链，对最底层造成 10 倍的放大冲击。排查 P0 故障时，不应只盯着报错的服务本身（user-service），要追踪整个调用链。

---

## INC-2026-0618: Redis 缓存击穿导致 order-db 过载

**发生时间**: 2026-06-18 10:15-11:02（持续 47 分钟）
**等级**: P1-High
**影响**: 下单成功率降至 63%，数据未丢失
**值班人**: wang-wu

### 根因

运营团队在 10:00 推送了全量用户促销通知，瞬时流量是平时的 8 倍。Redis 中的一个热门 key（当日促销商品库存）过期，大量请求同时穿透缓存查询 order-db 的同一行数据，导致 order-db CPU 飙至 98%，下单超时。

### Action Items

- [x] 热门 key 加逻辑过期（物理不删除，后台异步刷新） ✅ 2026-06-20
- [x] 促销活动前通知运维团队做容量评估 ✅ 流程已纳入
- [ ] order-db 读写分离 —— **已排期 9 月迭代**

### 经验教训

**缓存击穿 vs 缓存雪崩**: 本次是单 key 击穿而非大规模雪崩。单点热点 key 的防护方案是逻辑过期 + 互斥锁，而不是简单的加 TTL。运营活动前必须提前预热缓存。

---

## INC-2026-0522: user-db 主从延迟导致脏读

**发生时间**: 2026-05-22 20:00-21:15
**等级**: P2-Medium
**影响**: 约 3% 用户注册后短时间内查询不到自己的信息

### 根因

user-db 主库的 binlog 同步延迟在高峰时段达到 120 秒，从库数据滞后导致部分用户注册后立即查询返回空结果。排查发现从库磁盘 IO 已跑满（varchar 大字段批量更新产生的 binlog 量远超预期）。

### Action Items

- [x] 从库升级 SSD（从 HDD 迁移） ✅ 2026-06-01
- [x] 注册后关键查询改为强制走主库 ✅ 2026-05-25
- [x] 增加主从延迟监控，延迟 > 30 秒触发 P2 告警 ✅ 2026-06-05

### 经验教训

注册-登录这种"写后即读"的链路必须走主库。从库延迟不可预测，不能牺牲关键路径的一致性换性能。
