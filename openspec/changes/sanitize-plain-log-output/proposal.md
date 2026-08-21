## Why

`emit_event` 已对结构化事件脱敏，但 `logger.info/exception("...%s", config)` 等非结构化调用不经过 `_redact`——异常栈、config 对象可能把 apiKey/secret/token 直接打印到日志。

## What Changes

- 新增 `SanitizingFormatter`（logging Formatter 子类）：对渲染后的 message（含 args 展开值）做文本脱敏
- `_redact_text` 正则替换敏感键值对（`key: value` / `key=value`，含 JSON 结构）
- `configure_structured_logging` 的 handler 改用 `SanitizingFormatter`

## Capabilities

纯日志安全加固，不修改任何产品行为或 API 契约，`skip_specs: true`。

## Impact

- observability.py：新增 formatter 与文本脱敏
- 新增 tests/test_observability.py 覆盖脱敏与不误伤场景
