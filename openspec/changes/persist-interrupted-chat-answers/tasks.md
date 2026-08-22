## 1. partial 回答持久化

- [x] 1.1 _persist_interrupted_answer + 两个异常分支接入
- [x] 1.2 契约 ChatMessageMetadata 加 interrupted 可选字段

## 2. 测试

- [x] 2.1 新增回归测试（中断后 partial 已持久化带标记）
- [x] 2.2 更新既有 safe error 测试为新语义

## 3. 验证与记录

- [x] 3.1 ruff/pyright/全量 pytest（231 passed）/契约 25 /前端 82 通过
- [x] 3.2 更新 solution4.md 问题13 标记完成与 WIKI
