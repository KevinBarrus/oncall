## 1. 回滚测试

- [x] 1.1 单步回滚测试（downgrade -1 + upgrade head，版本断言）
- [x] 1.2 全链回滚测试（downgrade base + upgrade head，schema 断言）

## 2. 验证与记录

- [x] 2.1 实测 26 个迁移全链回滚可执行（无单向迁移）
- [x] 2.2 全量 ruff/pyright/pytest 通过；更新问题 15 记录与 WIKI
