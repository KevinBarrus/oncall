## 1. 权限收紧

- [x] 1.1 `_restrict_sqlite_file_permissions`：预创建 + chmod 0600
- [x] 1.2 `_sqlite_database_path`：绝对/相对/:memory: 解析

## 2. 验证与记录

- [x] 2.1 tests/test_database.py：新文件 0600、已存在文件收紧、:memory: 跳过、路径解析
- [x] 2.2 全量 ruff/pyright/pytest 通过；更新问题 12 记录与 WIKI
