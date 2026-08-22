## 1. CAS 归档

- [x] 1.1 archive_compacted_messages 接口改 message_ids + SQLite 实现 CAS 校验
- [x] 1.2 chat/memory.py 调用方传摘要覆盖 ID 集合

## 2. 入队去重

- [x] 2.1 _schedule_chat_memory_compaction 默认去重（queued/running 跳过）
- [x] 2.2 手动 memory:compact 端点 dedupe=False

## 3. 回归测试

- [x] 3.1 CAS 拒绝陈旧 ID 集（内联先归档 + 新消息补齐场景）且不误删新消息
- [x] 3.2 同会话重复入队返回 None；不同会话/不同 owner 不受影响

## 4. 验证与记录

- [x] 4.1 ruff/pyright/全量 pytest（224 passed）通过
- [x] 4.2 更新 solution4.md 问题2 标记完成与 WIKI
