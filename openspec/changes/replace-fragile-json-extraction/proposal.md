## Why

Planner 与记忆压缩依赖贪婪 `re.search(r"\{.*\}")` 从模型自由文本抠 JSON，模型输出带 Markdown 围栏或前后缀、或字符串内含 `}` 时可能抓错范围或解析失败，生产级应走结构化输出或受限解析。

## What Changes

- 新增 `super_ai/llm/json_output.py` 宽容 JSON 提取：整体解析 → ```json 代码块 → 括号配平（字符串感知）
- Planner prompt 改为严格 JSON-only，解析失败重试一次，仍失败降级 generic plan
- 记忆压缩 prompt 强化，`_validated_memory_document` 改用宽容提取，失败保留旧记忆

## Capabilities

纯结构化输出解析改进，不修改任何产品能力或 API 契约，`skip_specs: true`。

## Impact

- 新增 llm/json_output.py 与 tests/test_json_output.py
- 诊断 Planner 与聊天记忆压缩解析路径
- OpenSpec WIKI 与问题 24 记录
