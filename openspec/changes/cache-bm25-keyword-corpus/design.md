## Context

当前每次 `_keyword_recall` 都 `list_chunks` 和创建 `BM25L`。系统没有知识库版本或失效通知，因此本变更采用 60 秒进程内缓存。

## Decisions

- 缓存键为 tenant 与排序后的 knowledge base IDs，避免跨 owner/知识库复用
- 缓存 chunk 与预构建 BM25 语料；无额外过滤时直接复用 scorer
- 有 document/metadata 过滤时从缓存 chunk 过滤后按现有逻辑临时评分，优先正确性

## Non-Goals

- 不实现版本化即时失效或替换 Milvus 全量读取机制
- 不新增依赖、持久化或外部检索服务
