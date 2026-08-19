## Context

所有 SQLite repository 都通过 `create_memory_engine` 创建异步 SQLAlchemy 引擎，但该工厂未设置 SQLite 的连接参数或 pragma。

## Goals / Non-Goals

**Goals:**
- 在一个共享入口配置所有 SQLite 连接
- 让锁竞争等待而非立即失败，并强制现有外键定义

**Non-Goals:**
- 不把 SQLite 变成多主写库，不承诺高写入吞吐
- 不修改 SQLite schema 或暴露运行时配置

## Decisions

使用 SQLAlchemy connect event 在每条 SQLite DB-API 连接设置 pragma，使用 aiosqlite 的原生 `timeout` 参数设置锁等待。仅对 SQLite URL 应用该行为，避免影响其他数据库方言。

## Risks / Trade-offs

- [长写事务仍会阻塞其他写入] → 5 秒后明确失败；需要更高吞吐时迁移到服务型数据库
- [内存 SQLite 不支持 WAL] → 仅文件数据库验证 WAL，外键和 busy timeout 仍按连接设置
