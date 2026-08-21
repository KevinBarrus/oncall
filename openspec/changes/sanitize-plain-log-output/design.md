## Context

solution3.md 问题10：`emit_event` 已用 `_redact` 脱敏结构化事件，但非结构化 `logger.info/exception` 不受保护。方案：全局日志 Formatter/Filter 统一脱敏 + 测试。

## Goals / Non-Goals

**Goals:**

- 所有 super_ai 命名空间的日志输出（含 args 展开值）不泄漏敏感键值
- 保留 JSON 键值结构，仅替换敏感值

**Non-Goals:**

- 不脱敏其他命名空间（uvicorn/httpx 等）的日志
- 不追求机器级 JSON 保真（日志是人工可读流，格式微损可接受）

## Decisions

- `SanitizingFormatter.format` 先 `record.getMessage()` 渲染（含 args 值），脱敏后回填 `record.msg` 并清空 `record.args`，再走父类格式化
- `_redact_text` 正则：key 词根（`apiKey`/`secret`/`password`/`token`/`*_key` 等，大小写不敏感，`token`/`key` 独立词也脱敏——安全优先），分隔符 `:`/`=`，值捕获到空白/逗号/引号边界，保留引号结构
- 挂在 `configure_structured_logging` 的 super_ai handler 上，子 logger 通过传播继承

## Risks / Trade-offs

- [`key`/`token` 独立词误伤] → 如 "token=5000" 被脱敏，属安全优先的可接受代价
- [值含复杂字符（空格/引号）] → 值捕获到边界即止，残余片段仍可能出现在日志，但完整密钥值已覆盖

## Migration Plan

无 schema 变更。handler 格式化器替换对既有事件输出无影响（emit_event 已先脱敏）。
