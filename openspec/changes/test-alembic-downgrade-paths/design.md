## Context

solution3.md 问题15：迁移 downgrade 未被测试。方案：CI 增加 `upgrade head && downgrade -1 && upgrade head`；含数据转换的迁移 downgrade 明确 `raise NotImplementedError` 并注明单向。

## Goals / Non-Goals

**Goals:**

- 单步回滚（最新迁移）与全链回滚（base）均可执行且 schema 恢复
- 发现问题迁移时明确单向标注

**Non-Goals:**

- 不修改既有迁移（实测全链回滚成功，无单向迁移需要处理）
- 不引入独立 CI job（测试随 pytest 全量运行）

## Decisions

- 单步测试：`downgrade -1` 后 `upgrade head`，通过 `alembic_version` 表断言版本回到 head（`command.current` 打印但不返回值，改用 SQL 查询）
- 全链测试：`downgrade base` 后 `upgrade head`，断言 `REQUIRED_MEMORY_TABLES` 完整
- 实测验证：26 个迁移全部实现 downgrade 且可执行（无数据转换迁移）

## Risks / Trade-offs

- [全链回滚测试耗时] → SQLite 本地迁移，约数秒，CI 预算可接受
- [SQLite DDL 非事务性] → 失败迁移可能留下半状态；测试在 tmp 数据库运行，不影响真实数据

## Migration Plan

无迁移变更。
