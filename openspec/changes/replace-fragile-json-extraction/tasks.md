## 1. 提取工具

- [x] 1.1 新增 llm/json_output.py 宽容 JSON 提取（代码块、括号配平）

## 2. 解析路径

- [x] 2.1 Planner prompt 严格 JSON-only，`_validated_plan_with_sop_ids` 改用宽容提取并重试一次
- [x] 2.2 记忆压缩 prompt 强化，`_validated_memory_document` 改用宽容提取

## 3. 验证与记录

- [x] 3.1 新增 tests/test_json_output.py，相关回归与全量通过
- [x] 3.2 更新问题 24 方案与 WIKI
