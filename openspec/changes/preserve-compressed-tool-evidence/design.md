## Context

见 proposal.md。现有工具审计只保存有限摘要，不能承担完整日志原文；把原文继续放进工具结果会抵消压缩效果。

## Goals / Non-Goals

**Goals:** 保存可追溯原文、保持 owner/session 隔离、支持 Agent 按需展开。

**Non-Goals:** 不建立外部对象存储，不对未压缩输出重复持久化，不实现跨轮证据检索策略。

## Decisions

新增 SQLite `compressed_tool_evidence` 表，保存 owner、session、原文 JSON、哈希和压缩元数据。工具包装在压缩前写入该表，返回 `{content, _compression:{evidenceId,...}}`。请求作用域的 `read_tool_output_evidence` 工具与 API 都通过同一 Repository 按 owner/session 读取。

原文使用 JSON 字段保存，兼容字符串和结构化输出；不复用 `tool_call_audits.result_summary`，以免破坏其“有限摘要”语义。

## Risks / Trade-offs

- [SQLite 增长] → 仅保存实际被压缩的输出，并在后续历史保留策略中统一清理。
- [Agent 误读无关证据] → 展开工具只能读取当前会话且必须提供 evidence ID。

## Migration Plan

新增 Alembic revision；回滚时删除证据表。现有审计与聊天记录无需回填。
