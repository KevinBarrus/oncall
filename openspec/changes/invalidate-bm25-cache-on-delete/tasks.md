## 1. 失效机制

- [x] 1.1 `KnowledgeRetrievalTool.invalidate_keyword_cache`
- [x] 1.2 删除路径接入（向量删除成功后失效，独立 try/except 保护）
- [x] 1.3 `_retrieval_tool` provider 与 app.state 缓存，chat runner 复用

## 2. 验证与记录

- [x] 2.1 测试：缓存命中后显式失效，下次检索重建 corpus
- [x] 2.2 全量 ruff/pyright/pytest 通过；更新问题 8 记录与 WIKI
