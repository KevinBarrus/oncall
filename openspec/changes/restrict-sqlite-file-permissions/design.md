## Context

solution3.md 问题12：数据库文件权限由 umask 决定可能过宽。方案：`create_memory_engine()` 或启动脚本显式限制（如 0600）+ 部署文档补充。

## Goals / Non-Goals

**Goals:**

- SQLite 文件数据库权限强制 0600（首次创建与已存在均覆盖）
- `:memory:` 与绝对/相对路径正确跳过或解析

**Non-Goals:**

- 不实现磁盘加密（部署文档已建议，超出应用层职责）
- 不修改启动脚本（引擎层已覆盖所有连接路径）

## Decisions

- 在 `create_memory_engine` 的 sqlite 分支调用 `_restrict_sqlite_file_permissions`：预创建文件（0600）+ 强制 chmod，覆盖首次与已存在两种场景
- `_sqlite_database_path` 对齐 SQLAlchemy 语义：4 斜杠（`//`）绝对、3 斜杠相对 CWD、`:memory:` 跳过
- 权限操作 OSError 静默——加固失败不破坏引擎创建（依赖方容错）

## Risks / Trade-offs

- [Windows chmod 语义不同] → 测试标注 skipif；生产目标为 Linux/macOS
- [预创建空文件] → 与 SQLite 首次连接行为一致，无实质影响

## Migration Plan

无 schema 变更。
