## 1. 生成器

- [x] 1.1 `sync_error_catalog.py`：确定性输出 error-catalog.json
- [x] 1.2 提交生成的 JSON（12 个错误码）

## 2. 一致性校验

- [x] 2.1 契约测试双向断言（前端码 == 后端码，字段一致）
- [x] 2.2 CI 加生成校验（git diff --exit-code）

## 3. 记录

- [x] 3.1 全量 ruff/pyright/pytest/契约/前端通过
- [x] 3.2 更新问题 13 记录与 WIKI
