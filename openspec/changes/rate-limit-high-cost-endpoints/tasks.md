## 1. 限流器

- [x] 1.1 SlidingWindowLimiter（per-user 滑动窗口，线程安全）
- [x] 1.2 create_rate_limit_dependency 依赖工厂

## 2. 端点接入与错误码

- [x] 2.1 chat 流 / AIOps 诊断 / 文档上传接入
- [x] 2.2 RATE_LIMIT_EXCEEDED 错误码三端同步（error_catalog/errors.ts/生成 JSON/前端文案）

## 3. 验证与记录

- [x] 3.1 测试：限流器放行/拒绝/窗口过期、端点 429 集成
- [x] 3.2 全量 ruff/pyright/pytest/契约/前端通过；更新问题 24 记录与 WIKI
