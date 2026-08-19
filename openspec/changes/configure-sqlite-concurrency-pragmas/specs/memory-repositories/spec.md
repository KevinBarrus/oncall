## ADDED Requirements

### Requirement: SQLite connection concurrency and integrity settings
SQLite memory 引擎 SHALL 在每条文件数据库连接上启用 WAL、foreign key enforcement 和至少 5 秒的锁等待，以支持本地并发读写并保持关联记录完整性。

#### Scenario: File-backed SQLite connection is configured
- **WHEN** 后端创建一个文件 SQLite memory engine 并打开连接
- **THEN** 连接 MUST 报告 `journal_mode=wal`、`foreign_keys=1` 和不小于 5000 毫秒的 `busy_timeout`

#### Scenario: Foreign key constraint is enforced
- **WHEN** 一条记录引用不存在的 memory 父记录
- **THEN** SQLite MUST 拒绝该写入
