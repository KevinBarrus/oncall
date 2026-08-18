# 问题 2：解决方案

## 计划

1. 建立预算模型：历史输入、工具调用、工具结果、模型输出预留和安全余量分开计算。
2. 在 Agent 运行前预留输出预算，不把 95% 当作可用满载值。
3. 在每轮工具调用后重新计算剩余预算，达到阈值时停止继续调用或先压缩。
4. 优先使用当前模型 tokenizer；无法使用时保留近似估算并扩大安全余量。
5. 将预算信息写入审计和 SSE 状态，便于定位窗口超限原因。

## 验收标准

- 工具调用前后都能得到剩余上下文预算。
- 超预算时不会继续发起不可执行的模型请求。
- 预算估算覆盖工具消息和输出预留。

## 实施记录

- 新增 `ChatRuntimeContextBudget`，初始统计 system prompt、记忆摘要和历史消息。
- 运行时输入安全线按上下文窗口的 90% 计算，并固定预留 2048 个输出 token。
- LangChain 事件流中继续累计工具参数、工具结果、错误结果和模型流式输出。
- 超过预算时抛出运行时上下文超限异常，由聊天 SSE 返回 `CHAT_CONTEXT_LIMIT_REACHED`，不再继续消耗模型调用。
- 预算仍使用 LangChain 的近似 token 统计函数；真实模型 tokenizer 接入留作后续增强。

## 验证记录

- `uv run pyright src/super_ai/chat/memory.py src/super_ai/chat/streaming.py`：通过。
- `uv run ruff check src/super_ai/chat/memory.py src/super_ai/chat/streaming.py tests/test_chat_memory.py`：通过。
- `uv run pytest -q tests/test_chat_memory.py -k 'runtime_context_budget or compaction_selects_bounded or tool_compression'`：4 passed。
- `git diff --check`：通过。
