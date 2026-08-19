## Context

应用会复用 `QwenOpenAIProvider`，但 `check_readiness()` 每次都创建模型并执行一次 `ainvoke`。`/ready` 和 `/config/check` 均会调用该方法。

## Goals / Non-Goals

**Goals:**

- 有效期内复用安全 readiness 结果，降低付费模型调用
- 并发请求合并为一次探测
- 缓存过期后重新检查，保留现有安全错误语义

**Non-Goals:**

- 不跨进程共享缓存
- 不新增配置字段、后台探测任务或外部缓存
- 不改变 readiness 的 HTTP 状态或响应字段

## Decisions

- `QwenOpenAIProvider` 用 30 秒 TTL 保存最近的成功或失败 `LlmReadinessResult`
- 使用一个 `asyncio.Lock`，进入锁前后各检查一次缓存，避免并发击穿
- 结果仍由现有 `_safe_error_message` 生成，缓存不保存密钥或原始模型响应

## Risks / Trade-offs

- 最多 30 秒内会返回最近一次的状态；这是减少高频付费探测与保持恢复及时性的折中
- 缓存仅在单应用进程生效；多进程部署仍各自探测一次

## Migration Plan

1. 部署后首次探测填充缓存，无数据迁移
2. 回滚代码即可恢复逐请求探测
