## Context

solution3.md 问题24：无速率限制，恶意用户可耗尽 LLM 配额或后台队列。方案：高成本端点加 per-user 限流（如 10/minute），超限 429。

## Goals / Non-Goals

**Goals:**

- 三个高成本端点 per-user 限流
- 超限返回标准 429 错误（`RATE_LIMIT_EXCEEDED`）

**Non-Goals:**

- 不引入 slowapi/fastapi-limiter（需 Redis 或额外依赖）；进程内滑动窗口对单实例足够
- 不限制认证/低频端点（登录失败已有账号锁，其余端点成本低）

## Decisions

- `SlidingWindowLimiter`：per-key deque 时间戳 + threading.Lock，窗口内计数超限拒绝
- `create_rate_limit_dependency(scope, limit, window)`：工厂生成 FastAPI 依赖（闭包持独立 limiter，每个端点独立配额），内部依赖 `current_user`
- 配额：chat_stream=10/min、aiops_diagnose=10/min、document_upload=20/min
- 错误码 `RATE_LIMIT_EXCEEDED`（validation, 429）——复用问题13 的同步机制（error_catalog → 生成 JSON → errors.ts → 契约双向测试）

## Risks / Trade-offs

- [进程内限流多实例失效] → 单实例架构（部署文档已说明）；多进程时退化为尽力而为
- [限流器内存增长] → 键数 = 活跃用户 × 端点数，deque 有窗口内上界，可接受

## Migration Plan

无 schema 变更。错误码新增走既有同步链路。
