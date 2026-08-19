## Why

BM25 检索每次查询都会从 Milvus 拉取全量 chunk 并重建词法索引，知识库增大后延迟与 CPU 成本线性增长。

## What Changes

- 按 owner 与知识库集合短期缓存 BM25 语料和 scorer
- 对未使用文档或元数据过滤的查询复用 scorer
- 保留过滤查询的正确性，不新增检索后端

## Capabilities

### New Capabilities
- 无

### Modified Capabilities
- `knowledge-retrieval-tool`: BM25 语料在有效期内复用

## Impact

- 影响 hybrid retrieval、检索工具、测试与文档
