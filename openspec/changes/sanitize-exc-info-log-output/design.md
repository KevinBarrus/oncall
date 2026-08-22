## Context

solution4.md 问题6（P2，需验证）：`SanitizingFormatter.format`（observability.py:157-161）只脱敏 `record.getMessage()`；已核实当前无 `logger.exception`/`exc_info` 调用点，属潜在缺口。方案：对 `formatException` 与 `stack_info` 拼接结果同样过 `_redact_text`。

## Goals / Non-Goals

**Goals:**

- 含 exc_info 的日志输出（堆栈文本）不泄漏敏感键值
- 现有行为不回退（消息、args、普通文本脱敏不变）

**Non-Goals:**

- 不改第三方命名空间日志（uvicorn/langchain 不经该 formatter，与 solution3 声明范围一致）
- 不扫描堆栈之外的二进制/对象 repr（文本脱敏按既有 `_SENSITIVE_VALUE_PATTERN` 语义）

## Decisions

- `format()` 返回 `_redact_text(super().format(record))`——对包含 exc_text/stack_info 的完整渲染结果整体再脱敏一次；`record.msg`/`record.args` 的处理保持原样
- 测试构造真实 `sys.exc_info()` 记录，断言堆栈中的 `secretKey` 值被替换

## Risks / Trade-offs

- [重复 regex 开销] → 日志频率低，且仅在 ERROR 路径（含堆栈）多一次扫描，可接受
- [堆栈行内敏感值格式多变] → 与既有文本脱敏同一模式，覆盖 key: value / key=value；无法匹配的极端格式仍可能泄漏，但比现状更严

## Migration Plan

无。
