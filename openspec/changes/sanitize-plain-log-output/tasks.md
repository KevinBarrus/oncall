## 1. 脱敏机制

- [x] 1.1 `SanitizingFormatter`：渲染后 message 脱敏并回填
- [x] 1.2 `_redact_text`：敏感键值对正则替换（JSON 与 `=` 风格）
- [x] 1.3 `configure_structured_logging` 接入新 formatter

## 2. 验证与记录

- [x] 2.1 新增 tests/test_observability.py（JSON 键值、args 展开、`=` 风格、普通文本不误伤、集成输出）
- [x] 2.2 全量 ruff/pyright/pytest 通过
- [x] 2.3 更新问题 10 方案与 WIKI
