## 1. 脱敏加固

- [x] 1.1 SanitizingFormatter.format 对 super().format 完整结果二次脱敏

## 2. 回归测试

- [x] 2.1 exc_info 堆栈中敏感键值被脱敏（含 RuntimeError 保留）

## 3. 验证与记录

- [x] 3.1 ruff/pyright/全量 pytest（226 passed）通过
- [x] 3.2 更新 solution4.md 问题6 标记完成与 WIKI
