## Context

solution4.md 问题1（P1）：`LangChainChatAgentRunner.stream` 对全部工具套 `_wrap_tool_output_compression`，其中 `read_tool_output_evidence` 返回的原文（`evidence.content`，str）被再次压缩成 `[compressed]` 摘要并写入新 evidence 行，展开回路失效。

## Goals / Non-Goals

**Goals:**

- 证据展开工具返回原文（与 evidence.content 完全相等）
- Skill 指令工具保留原文

**Non-Goals:**

- 不改变其他工具（知识检索/read_document/MCP 等大输出仍压缩 + evidence 展开，这是既有设计）

## Decisions

- 豁免名单用**工具名**判定（`frozenset` 常量，位于 `_wrap_tool_output_compression` 上方），在 wrapper 入口直接 `return tool`——语义内聚且可单测
- 覆盖两个自指工具：`read_tool_output_evidence`（返回原文）、`load_skill`（返回指令原文）
- 回归测试断言 `wrapped is tool`（修复前被替换为压缩 coroutine）+ 完整调用结果等于原文

## Risks / Trade-offs

- [名单用名称而非结构判定] → 工具名在本项目内唯一（ToolRegistry 同名限定），新增自指工具时需同步名单；已在 docstring 说明
- [跳过包装的大输出 Skill 内容膨胀上下文] → SKILL.md 单文件受 64KB 限制，且系统提示词预算预检已覆盖（问题19），可接受

## Migration Plan

无 schema 变更。
