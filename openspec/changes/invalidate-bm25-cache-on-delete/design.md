## Context

solution3.md 问题8：文档删除后 60s 窗口内 BM25 缓存命中旧 corpus。方案：删除/索引完成时主动失效，或缓存键加版本号。

## Goals / Non-Goals

**Goals:**

- 文档删除后立即失效对应 `(owner_user_id, knowledge_base_ids)` 缓存
- 删除主操作（向量清理）不受失效影响

**Non-Goals:**

- 不改用知识库版本号方案（改动面大，主动失效已覆盖主要场景）
- 不处理索引完成失效（后台任务无 retrieval tool 引用，60s TTL 兜底，向量检索不受影响）

## Decisions

- `invalidate_keyword_cache` 按与缓存键相同的 `(owner_user_id, sorted(kb_ids))` 精确删除
- 失效调用放在向量删除成功之后、独立 try/except 保护——失效失败静默（60s TTL 兜底），绝不破坏删除流程
- `_retrieval_tool` provider 惰性创建并缓存 `app.state`，`_chat_agent_runner` 复用同一实例（保证失效命中真实缓存）
- 用 `getattr` 访问 state（避免未初始化 AttributeError）

## Risks / Trade-offs

- [索引完成不失效] → 新文档 60s 内不参与 BM25（向量检索即时生效），窗口内 RRF 缺新文档 BM25 分，影响小
- [失效尽力而为] → 与删除主操作解耦，失败有 TTL 兜底

## Migration Plan

无 schema 变更。
