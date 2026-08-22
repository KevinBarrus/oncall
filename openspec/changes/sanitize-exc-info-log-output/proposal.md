## Why

`SanitizingFormatter.format` 只对 `record.getMessage()` 渲染文本脱敏，`super().format()` 追加的 `exc_info` 堆栈与 `stack_info` 不过 `_redact_text`。当前 `super_ai` 命名空间无 `logger.exception`/`exc_info` 调用点（潜在缺口非现行泄漏），但未来任何调用点引入含密钥的异常消息（URL/config repr）将原样进日志。

## What Changes

- `SanitizingFormatter.format` 对 `super().format(record)` 完整结果（含堆栈）再做一次 `_redact_text`
- 回归测试：`exc_info` 堆栈中 `{"secretKey": "..."}` 被脱敏

## Capabilities

异常堆栈文本脱敏，`skip_specs: true`。

## Impact

- observability.py（format 二次脱敏）
- tests/test_observability.py（1 个回归测试）
