## 1. 生命周期清理

- [x] 1.1 clear_messages 事务内删除压缩证据与工具审计行

## 2. 证据去重

- [x] 2.1 evidence create 按 (会话, source_hash) 去重返回已有行

## 3. 回归测试

- [x] 3.1 同 hash 两次 create 同一行；clear 后 evidence/audit 为空

## 4. 验证与记录

- [x] 4.1 ruff/pyright/全量 pytest（228 passed）通过
- [x] 4.2 更新 solution4.md 问题8 标记完成与 WIKI
