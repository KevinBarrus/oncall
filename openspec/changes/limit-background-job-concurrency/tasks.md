## 1. 限流机制

- [x] 1.1 `claim_next` 支持按 kind 过滤（接口 + SQLite 实现）
- [x] 1.2 `BackgroundJobRuntime` 增加 `max_concurrent_per_kind` 与 `_active_by_kind` 计数

## 2. 竞态与配置

- [x] 2.1 `_claim_available` 以 `asyncio.Lock` 串行化检查-领取-计数
- [x] 2.2 app.py 为三种任务类型配置上限 1

## 3. 验证与记录

- [x] 3.1 新增 per-kind 并发限流测试（并发触发同类任务，断言峰值不超过上限）
- [x] 3.2 更新问题 6 方案与 WIKI
