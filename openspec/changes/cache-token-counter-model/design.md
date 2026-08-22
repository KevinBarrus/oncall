## Context

solution4.md 问题10（P2，性能）：`provider.py:101-107` 每次 `count_tokens` 调 `create_chat_model()`；`chat/memory.py:729-765` 压缩选段逐条估算。

## Goals / Non-Goals

**Goals:**

- token 计数复用同一个模型实例（消除重复构造开销）
- 保持 `count_tokens` 接口与语义不变

**Non-Goals:**

- 不缓存 `estimate_context_tokens` 结果（上下文会变化，缓存无效）
- 不改变 `create_chat_model` 本身（调用方仍拿新实例，无共享状态污染）

## Decisions

- `__init__` 加 `_token_counter_model: ChatModel | None = None`；`count_tokens` 首次惰性 `self.create_chat_model()` 后复用
- tokenizer 计数为纯函数（无状态），asyncio 单线程下无锁缓存安全

## Risks / Trade-offs

- [缓存模型跨请求复用] → tokenizer 无状态只读，无安全风险
- [配置变更后缓存陈旧] → provider 实例随配置创建，配置不变实例不变（与既有 readiness 缓存同生命周期）

## Migration Plan

无。
