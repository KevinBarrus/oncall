## Why

跨轮工具证据注入（`_cross_turn_evidence_context`）按 4000 字符直接截断，可能截到一行中间；同一工具调用结果或同一引用可能重复注入，浪费上下文预算。

## What Changes

- 审计行按 `(tool_name, result_summary)` 去重，citation 行按引用 ID 去重
- 行级预算：逐行估算长度，超限整条丢弃（不截半），无 `content[:4000]` 截断

## Capabilities

纯内部上下文组装改进，不修改任何契约或用户可见行为，`skip_specs: true`。

## Impact

- chat/streaming.py `_cross_turn_evidence_context`
- 新增去重与整条丢弃测试
