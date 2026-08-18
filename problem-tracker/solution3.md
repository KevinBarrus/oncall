# 问题 3：解决方案

## 计划

1. 保留当前自由摘要作为短期兼容字段。
2. 增加结构化记忆：用户目标、已确认事实、当前决策、未完成事项、引用来源、最近上下文。
3. 每条结构化记忆记录保存来源消息 ID、创建时间、状态和置信度。
4. 新决策显式标记替代旧决策，不把冲突内容简单拼接。
5. 压缩后做结构校验和关键事实回归检查；失败时保留旧摘要，不覆盖有效记忆。

## 验收标准

- 关键事实可以回指原始消息。
- 新旧决策关系可查询。
- 摘要失败或校验失败不会破坏已有记忆。
- 原始历史仍可完整恢复。

## 实施记录

- 将记忆摘要格式升级为版本化 JSON：`version`、`summary` 和 `items`。
- `items` 按目标、事实、决策、待办、来源和最近上下文分类，并要求保存 `sourceMessageIds`。
- 摘要 prompt 为每条新增消息注入消息 ID，模型只能引用当前批次或已有记忆中的来源 ID。
- 记忆进入模型上下文时渲染为可读文本，同时保留结构化来源信息。
- JSON 解析失败、版本错误、分类错误、来源 ID 不存在或摘要过长时，拒绝覆盖旧摘要。
- 保留旧版自由文本摘要的读取兼容性；旧摘要作为无结构来源的 legacy 摘要使用。

## 验证记录

- `uv run ruff check src/super_ai/chat/memory.py tests/test_chat_memory.py`：通过。
- `uv run pyright src/super_ai/chat/memory.py src/super_ai/chat/streaming.py`：通过。
- `uv run pytest -q tests/test_chat_memory.py -k 'structured_memory or compaction_selects_bounded or runtime_context_budget or tool_compression'`：5 passed。
- `git diff --check`：通过。
