# 问题 4：解决方案

## 计划

1. 将工具结果包装成统一的 `ToolOutputEnvelope`，区分完整、结构化裁剪、LLM 摘要和降级结果。
2. 保存 sourceHash、原始长度、结果数量、采样范围、压缩方式和原始证据引用。
3. 对 JSON 工具结果优先做字段级裁剪，不先转成自由文本；保留机器可读字段。
4. AIOps 关键证据默认只做确定性结构化裁剪，LLM 只用于非关键补充摘要。
5. 保留原始结果在审计/证据存储中，模型只收到带引用的压缩视图。

## 验收标准

- 模型可以知道结果是否完整、采样或摘要。
- 每个压缩结果可回指原始工具调用和原始输出。
- JSON 关键字段和 SearchLog 证据字段不因通用文本压缩丢失。

## 实施记录

- 普通字符串工具结果压缩后返回结构化 envelope，包含 `content` 和 `_compression` 元数据。
- 结构化 JSON 工具结果不再先转换成普通文本；压缩后保留 `preserved` 字段和机器可读元数据。
- 压缩元数据包含 mode、sourceHash、originalChars 和 compressedChars。
- SearchLog 摘要增加结构化聚类采样模式、原始结果哈希和原始长度；解析失败也保留 rawPreview 和指纹。
- 原始工具结果仍由现有审计和证据链保存，压缩结果只作为 Agent 上下文视图。

## 验证记录

- `uv run ruff check src/super_ai/chat/memory.py src/super_ai/chat/streaming.py src/super_ai/aiops/diagnostics.py tests/test_chat_memory.py tests/test_aiops_diagnostics.py`：通过。
- `uv run pyright src/super_ai/chat/memory.py src/super_ai/chat/streaming.py`：通过。
- 聊天压缩相关测试：6 passed。
- SearchLog 压缩相关测试：4 passed。
- `git diff --check`：通过。
