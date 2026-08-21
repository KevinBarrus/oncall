## 1. 去重与预算

- [x] 1.1 审计行按 (tool_name, result_summary) 去重；citation 行按 ID 去重
- [x] 1.2 行级预算整条丢弃，移除整体截断

## 2. 验证与记录

- [x] 2.1 测试：重复审计/引用只注入一次、超预算整条丢弃
- [x] 2.2 全量 ruff/pyright/pytest 通过；更新问题 5 记录与 WIKI
