## MODIFIED Requirements

### Requirement: Hybrid retrieval ranks scoped knowledge
系统 SHALL 在当前 user 可访问的知识库范围内结合向量与 BM25 召回，并保留可解释排名字段。系统 MUST 在短期内按 owner 和知识库范围复用无过滤 BM25 语料，且不得跨作用域复用。

#### Scenario: Repeated scoped keyword retrieval
- **WHEN** 同一 owner 与知识库集合在缓存有效期内重复执行无过滤关键词检索
- **THEN** 系统 MUST 复用已加载的 chunk 语料和 BM25 索引，而不是再次全量加载并构建。

#### Scenario: Filtered keyword retrieval
- **WHEN** 查询包含文档或元数据过滤
- **THEN** 系统 MUST 仅使用满足过滤条件的 chunk 评分，不得因缓存返回范围外内容。
