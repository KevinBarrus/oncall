## Why

`/ready` 与 `/config/check` 的每次请求都会调用付费 LLM 完成探活。负载均衡器的高频探测会持续产生费用和延迟，且并发探测会放大调用次数。

## What Changes

- 在 LLM Provider 内缓存短期 readiness 结果
- 使用单飞锁让同一进程内并发探测复用一次模型调用
- 缓存过期后重新探测，继续返回安全的 provider 元数据

## Capabilities

### New Capabilities

- 无

### Modified Capabilities

- `runtime-readiness-checks`: LLM readiness 使用有限 TTL 缓存与并发合并

## Impact

- 影响 LLM Provider、其单元测试、问题追踪和 OpenSpec WIKI
- 不改变 `/ready` 的响应契约，不新增依赖或持久化状态
