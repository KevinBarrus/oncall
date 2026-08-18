# 问题 1：记忆压缩输入没有独立预算

## 评估

确认成立，高优先级。

`ChatMemoryService._compact_messages()` 将所有未压缩消息拼接成 transcript 后直接调用 LLM。`context_70_percent` 只控制正常 Agent 上下文估算，不限制摘要请求自身的输入长度。

## 影响

历史接近模型窗口时，摘要请求可能先失败；失败不会推进 `compacted_message_count`，后续请求会反复提交同一批超长历史，最终用户无法继续对话。

## 结论

这是线上长会话的真实正确性问题，不能只靠增加摘要 prompt 解决。
