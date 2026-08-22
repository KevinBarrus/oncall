## Context

solution4.md 问题12（P2）：`streaming.py:790-798` 与 `:815-822` evidence create 抛错冒泡，LangChain 记为工具错误，压缩结果被丢弃。

## Goals / Non-Goals

**Goals:**

- evidence 落库失败不影响工具调用（返回压缩摘要，无 evidenceId）
- 失败可观测（事件）

**Non-Goals:**

- 不重试 evidence 写入（会话内可展开能力降级为"摘要仍可用"，可接受）
- 不改存储层去重（问题8 已做）

## Decisions

- 两条路径（str / dict）各自包 try/except：失败 `emit_event(logger, "chat.tool_evidence.persist_failed", toolName=..., errorCategory=...)`，`evidenceId` 仅在 else 分支写入
- 测试：monkeypatch evidence_repo.create 抛 `sqlite3.OperationalError`，断言压缩摘要仍返回且无 evidenceId

## Risks / Trade-offs

- [落库失败后无法展开原文] → 工具结果以压缩摘要形式可用（尽力而为语义），与 LLM 压缩失败→采样回退一致；失败事件可观测

## Migration Plan

无。
