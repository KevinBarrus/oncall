## Context

solution3.md 问题17：确认项。原报告标 P0 未证实，复核发现 `search_chunks`/`list_chunks`/`delete_document_chunks` 全部强制显式 `tenant_id` + 知识库作用域参数，无 `count_chunks` 独立操作。方案：补"跨租户查询返回空"测试固化边界。

## Goals / Non-Goals

**Goals:**

- 以测试固化租户隔离边界（filter 互斥、转义安全）
- 确认未来新增 Milvus 操作沿用显式作用域参数的约定

**Non-Goals:**

- 不引入可执行 Milvus filter 的模拟器（filter 正确构造已被现有测试覆盖，执行正确性由 Milvus 保证）
- 不改动 MilvusVectorStore 代码（未发现缺口）

## Decisions

- 新增两个测试：
  - `test_tenant_filters_are_mutually_exclusive_between_tenants`：tenant_a filter 不含 user_b、tenant_b filter 不含 user_a
  - `test_tenant_filter_escapes_quotes_in_scope_values`：含引号的作用域值安全转义（防注入）
- 复核结论记录在案：数据访问方法签名强制 tenant 作用域

## Risks / Trade-offs

- [单测无法验证 Milvus 端执行] → filter 构造正确性是应用层可测部分；Milvus 端行为由其自身保证

## Migration Plan

无 schema 变更。
