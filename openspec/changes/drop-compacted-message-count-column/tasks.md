## 1. 迁移

- [x] 1.1 202608210003 drop column（downgrade 补回默认值）

## 2. 全链路清理

- [x] 2.1 ORM/record/update_memory_state/archive/clear/payload 删除字段
- [x] 2.2 memory.py 切片改直接使用 history
- [x] 2.3 契约 chat.ts/openapi.ts 删除 compactedMessageCount
- [x] 2.4 前后端测试清理（后端 6、前端 3）

## 3. 验证与记录

- [x] 3.1 ruff/pyright/全量 pytest（230 passed）/契约 25 /前端 82 /迁移回滚通过
- [x] 3.2 更新 solution4.md 问题11 标记完成与 WIKI
