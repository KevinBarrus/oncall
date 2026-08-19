## Why

SQLite 默认 rollback journal 和零等待写锁会使聊天、诊断和后台任务的并发写入产生 `database is locked`，且默认不强制外键。数据库连接层必须落实本地优先运行时的并发与完整性边界。

## What Changes

- SQLite 引擎连接启用 WAL、5 秒 busy timeout 和 foreign key enforcement。
- 为文件 SQLite 数据库补充 pragma 与外键级联回归测试。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `memory-repositories`: SQLite memory 连接具备并发等待和外键完整性设置

## Impact

- 影响统一数据库引擎工厂及其测试。
- 不新增配置、依赖、API 或 schema 迁移。
