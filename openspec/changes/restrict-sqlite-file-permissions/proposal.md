## Why

SQLite 数据库文件（`var/memory.sqlite3`）权限由 umask 决定，共享服务器上可能为 0644——数据库含密码哈希、token 哈希与聊天历史，存在被同机其他用户读取的风险。

## What Changes

- `create_memory_engine` 对 SQLite 文件 URL 预创建并 `chmod 0600` 数据库文件（含已存在文件强制收紧）
- 相对/绝对/`:memory:` URL 统一解析

## Capabilities

纯安全加固，不修改任何契约或用户可见行为，`skip_specs: true`。

## Impact

- memory/database.py 权限收紧与 URL 解析
- 新增 tests/test_database.py（权限、已存在文件、:memory:、路径解析）
