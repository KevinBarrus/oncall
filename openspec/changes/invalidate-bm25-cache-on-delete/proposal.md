## Why

`_keyword_corpora` 缓存 60s TTL，文档删除后 60s 窗口内 BM25 检索仍可能命中已删除文档的 corpus，与向量结果 RRF 融合后返回无效引用。

## What Changes

- `KnowledgeRetrievalTool` 新增 `invalidate_keyword_cache(owner_user_id, knowledge_base_ids)` 公开方法
- 文档删除路径（`_delete_document_vectors`）删除成功后主动失效对应缓存
- 抽取 `_retrieval_tool` provider 并缓存到 `app.state`，与 chat agent runner 共用同一实例

## Capabilities

纯内部缓存失效改进，不修改任何契约或用户可见行为，`skip_specs: true`。

## Impact

- retrieval/tool.py 失效方法
- api/app.py 删除路径接入 + provider 抽取
- 新增缓存失效测试
