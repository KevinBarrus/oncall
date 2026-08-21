## Why

Alembic 迁移的 downgrade 从未被测试——生产回滚失败只能事后发现；SQLite 部分 ALTER 受限，迁移回滚路径需要验证。

## What Changes

- `test_memory_migrations.py` 新增两个回滚测试：
  - 单步回滚：upgrade head → downgrade -1 → upgrade head，断言版本回到 head
  - 全链回滚：upgrade head → downgrade base → upgrade head，断言 schema 完整

## Capabilities

纯测试补强，不修改任何迁移或运行时行为，`skip_specs: true`。

## Impact

- tests/test_memory_migrations.py 新增回滚测试
- 全量验证：26 个迁移均可回滚（无单向迁移需 raise NotImplementedError）
