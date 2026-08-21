# 第三轮解决方案与实施计划

本文件与 `problem3.md` 的编号一一对应。方案以当前源码为事实，并已吸收 `problem3-feedback.md`（用户复核）与 `problem3-correction.md`（fable5 修正）的结论：原报告的 6 个 P0 经逐条核对全部不成立，修正后为 0 个 P0、4 个 P1、若干 P2。

## 推进顺序

1. 可靠性（P1）：问题7（AIOps 整图超时）、问题6（后台任务并发限制）。
2. 安全与运维（P1）：问题10（非结构化日志脱敏）、问题26（生产部署文档）。
3. 可观测与工程质量（P2，可选）：问题3、问题4、问题5、问题8、问题9、问题12、问题13、问题19、问题22、问题23、问题24、问题28。
4. 明确不实施：问题21、问题25、问题27（为不存在的场景预支复杂度）。

## 问题1的解决方案：推进 app.py 渐进拆分（非阻塞）

- 原报告标为 P0 阻塞 + 回归；复核确认这是 solution2.md 问题20 的明确决策（渐进拆分，已建 `api/dependencies.py` + `api/routers/` 模式，auth 域已示范）。
- 方案：维持"新增或修改路由时优先迁移"原则；在 chat/knowledge/aiops 任一域发生路由变更时，同步迁移该域全部路由，不一次性重写。

## 问题2的解决方案：会话执行租约（已实现，无需修复）

- 原报告误报（搜索方法名 `acquire_chat_session_lease` 错误）。
- 实际已实现：`chat/streaming.py:183` `acquire_execution_lease` 获取 15 分钟租约、`:191-193` 冲突返回 `CHAT_SESSION_BUSY`、`:204-206` finally 释放，与 solution2.md 问题13 一致。
- 结论：删除该问题。

## 问题3的解决方案：压缩失败可查询（P2 可选）

- 现状：压缩失败已发出结构化日志事件（`chat.compaction.failed`、`chat.tool_compression.fallback`），但未持久化到可查询表。
- 方案（可选）：`chat_sessions` 增加 `last_compaction_error`/`last_compaction_failed_at` 字段，失败时更新并在会话 memory API 返回；工具压缩失败在审计记录加 `compression_failed` 标记。
- 已完成：Alembic 迁移 `202608210001` 为 `chat_sessions` 增加 `last_compaction_error`/`last_compaction_failed_at`；硬限压缩失败时记录 error 与时间，成功压缩（archive）后清除。
- 已完成：session memory payload（`ChatMemoryState`）新增 `lastCompactionError`/`lastCompactionFailedAt`，前端契约与 mock 同步。
- 已完成：工具压缩降级（`sampled_fallback`）在 `_compression` metadata 增加 `compressionFailed` 标记，随审计 result_summary 持久化。
- 已补充测试：硬限压缩失败记录 error、成功压缩清除 error。

## 问题4的解决方案：审计失败可观测（P2 可选）

- 现状：`_persist_tool_call_audit` 失败只 emit `chat.tool_audit.failed` 事件，聊天继续。
- 方案（可选）：assistant 消息 metadata 写 `{"auditFailed": true, "auditError": "<safe_category>"}`，或会话级累积 `audit_failure_count` 并在会话 API 返回。
- 已完成：采用方案第二条路径——Alembic 迁移 `202608210002` 为 `chat_sessions` 增加 `audit_failure_count`（默认 0），审计持久化失败时递增（owner 作用域），内层 try/except 保证审计记账失败也不破坏聊天流。
- 已完成：session payload（`ChatSessionSummary`）新增 `auditFailureCount`，前端契约与 mock 同步。
- 已补充测试：审计持久化失败后会话计数递增。

## 问题5的解决方案：跨轮证据去重与截断（P2 可选）

- 现状：`_build_cross_turn_context()` 取最近 6 条审计 + 8 个 citation，按 4000 字符直接截断，未去重。
- 方案（可选）：按审计/citation ID 去重；改用 token-aware 整条丢弃式截断（不截半）。
- 已完成：审计行按 `(tool_name, result_summary)` 去重（同摘要不同调用视为重复），citation 行按引用 ID 去重。
- 已完成：行级预算——逐行估算长度，超限整条丢弃（不截半），移除 `content[:4000]` 整体截断。
- 已补充测试：重复审计/引用只注入一次、超预算整条丢弃。

## 问题6的解决方案：后台任务全局并发限制（P1，建议优先）

- 现状：`jobs/runtime.py` 无 semaphore/max_concurrent，批量任务可能同时写 SQLite 触发 `SQLITE_BUSY`，或打满 LLM/Milvus 配额。
- 方案：worker 增加 `max_concurrent_tasks`（默认 5），领取任务前检查执行中任务数，达到上限则等待；或按任务类型（`memory_compaction`、`document_indexing`、`aiops_diagnosis`）分别限流。
- 验证：并发触发 N 个任务，断言执行中数量不超过上限；恢复后继续处理。
- 已完成：`BackgroundJobRuntime` 增加 `max_concurrent_per_kind` 配置与执行中计数，`claim_next` 支持按 kind 过滤（接口 + SQLite 实现）；`_claim_available` 以 `asyncio.Lock` 串行化“检查槽位 → 领取 → 计数”，消除多 worker 竞态。
- 已完成：app.py 配置 `document_index`/`aiops_diagnosis`/`chat_memory_compaction` 各限 1，避免单一 kind 占满 worker。
- 已补充限流测试：并发触发同类任务断言峰值不超过上限。

## 问题7的解决方案：AIOps 整图 wall-clock 超时（P1，建议优先）

- 现状：`diagnostics.py` 图运行处无整体超时，LLM 卡住（模型 overload、网络抖动）会长期占用后台任务槽位。
- 方案：为整个 LangGraph 图执行加 `asyncio.timeout(600)`（10 分钟）；超时时生成降级报告“诊断超时，已收集的证据：...”，任务标记 `timed_out`，SSE 发送 `timeout` 事件。
- 验证：注入慢 LLM 桩（sleep 超过超时），断言任务进入 timed_out 且报告含已收集证据。
- 已完成：`AiopsDiagnosticService` 增加 `graph_timeout_seconds`（默认 600），图执行改为 deadline + `wait_for(__anext__)` 循环（Python 3.10 兼容），超时取消图并 `aclose()`。
- 已完成：`_handle_graph_timeout` 从 owner 作用域仓库读取已收集证据，持久化 `timed_out` 任务与 `_timeout_report_content` 降级报告，SSE 以 `report` → `task.status`（`timed_out`）→ `complete` 结束流；共享契约 `TaskStatusSseEvent.status` 增加 `timed_out`。
- 已补充超时测试：慢 Planner 桩 + 短超时，断言任务状态、降级报告含已收集证据、SSE 事件序列。

## 问题8的解决方案：BM25 缓存主动失效（P2 可选）

- 现状：`retrieval/tool.py` 的 `_keyword_corpora` 60s TTL，文档删除后 60s 窗口内可能命中已删除文档。
- 方案（可选）：文档删除/索引完成时主动失效对应 `(owner_user_id, knowledge_base_ids)` 缓存；或缓存键加入知识库版本号。
- 已完成：`KnowledgeRetrievalTool` 新增 `invalidate_keyword_cache(owner_user_id, knowledge_base_ids)`，文档删除路径（`_delete_document_vectors`）在向量清理成功后主动失效对应缓存；失效为尽力而为（独立 try/except + 60s TTL 兜底），不破坏删除主操作。
- 已完成：抽取 `_retrieval_tool` provider 缓存到 `app.state`，与 chat agent runner 共用同一实例，保证失效命中真实缓存。
- 已补充测试：缓存命中后显式失效，下次检索重建 corpus。
- 限制：索引完成路径未接入失效（后台任务无检索工具引用），新文档 60s 内不参与 BM25（向量检索即时生效，影响小）；缓存键版本号方案未采用。

## 问题9的解决方案：评测 mock fixture（P2 可选）

- 现状：`aiops_evaluation.py`/`rag_evaluation.py` 依赖真实 API（`AIOPS_EVAL_API_BASE_URL`/`RAG_API_BASE_URL`），离线无法调试指标逻辑。
- 方案（可选）：提供 `tests/fixtures/` mock 响应（3-5 案例），评测脚本加 `--mock` 参数走 fixture，CI 跑 mock 评测保证指标计算不回归。

## 问题10的解决方案：全局日志脱敏（P1，安全加固）

- 现状：`observability.py` 的 `emit_event` 已用 `_redact` 脱敏（覆盖 `_key`/`_secret`/`_token` 后缀），但 `logger.info/exception` 等直接调用不受保护。
- 方案：增加全局日志 Formatter/Filter，对 record 中的敏感 key（apiKey/secret/password/token 等）统一替换为 `***`；补充测试“日志输出不含真实密钥”。
- 验证：构造含 apiKey 的异常日志，断言输出被脱敏。
- 已完成：新增 `SanitizingFormatter`（渲染后 message 脱敏并回填，含 args 展开值），`_redact_text` 正则替换敏感键值对（JSON 与 `=` 风格，保留引号结构）；`configure_structured_logging` 的 handler 改用新 formatter，覆盖所有 super_ai 命名空间日志。
- 已补充脱敏测试：JSON 键值、args 展开、`=` 风格、普通文本不误伤、集成输出验证。

## 问题11的解决方案：Skill 上传校验（已实现，无需修复）

- 原报告误报。
- 实际已实现：`chat/configuration.py:91` `validate_skill_upload` 校验文件名严格 `SKILL.md`、64KB 大小限制、UTF-8 解码、YAML frontmatter（name/description）。
- 结论：删除该问题。恶意指令注入属 LLM 二道校验范畴，成本高，当前不实施。

## 问题12的解决方案：SQLite 文件权限（P2 可选）

- 现状：`var/memory.sqlite3` 权限由 umask 决定，共享服务器上可能过宽。
- 方案（可选）：`create_memory_engine()` 或启动脚本显式限制数据库文件权限（如 `0600`）；部署文档补充"生产建议：文件权限、磁盘加密"。

## 问题13的解决方案：错误码契约测试（P2 可选）

- 现状：`errors.ts` 与 `error_catalog.py` 双份手动同步，现有 `api-contracts.test.ts` 只测形状不测跨端一致性。
- 方案（可选）：新增契约测试断言后端 `/openapi.json` 的错误响应与 `errors.ts` 一致（前端错误码 ⊆ 后端实际错误码）。

## 问题14的解决方案：evidenceId 注入（已实现，无需修复）

- 原报告误报（自行标注"需验证"但未验证）。
- 实际已实现：`chat/streaming.py:769/793` 注入 `metadata["evidenceId"]`、`:658` 注册 `read_tool_output_evidence` 工具、`:835-851` 工具实现完整。
- 结论：删除该问题。

## 问题15的解决方案：迁移回滚路径测试（P2 可选）

- 现状：Alembic 迁移的 downgrade 未被测试。
- 方案（可选）：CI 增加 `alembic upgrade head && alembic downgrade -1 && alembic upgrade head`；含数据转换的迁移在 downgrade 明确 `raise NotImplementedError` 并注明单向。

## 问题16的解决方案：MCP 关闭旧客户端（已实现，无需修复）

- 原报告误报。
- 实际已实现：`mcp_connections.py:156` 配置替换时 `aclose()`、`:176` 应用关闭时清理、`:181-185` 统一 `aclose()`。
- 结论：删除该问题。

## 问题17的解决方案：Milvus 作用域过滤审查（P2，确认项）

- 原报告标 P0，复核未找到实际缺口（`search`/`list_chunks`/`delete_document_chunks` 全部强制显式 `tenant_id` + 知识库作用域）。
- 方案：保持现状；补充"跨租户查询返回空"测试固化该边界；如未来新增 `count_chunks` 等操作必须沿用显式作用域参数。

## 问题18的解决方案：报告生成降级（已实现，无需修复）

- 原报告误报。
- 实际已实现：`diagnostics.py:899` `_fallback_report_content`、`:1367` 完整降级报告逻辑。
- 结论：删除该问题。

## 问题19的解决方案：System Prompt 长度预检（P2 可选）

- 现状：Prompt/Skill 持久化时未预检组装后长度，用户可能在首次对话才遇到上下文超限。
- 方案（可选）：`POST /chat/prompts`、`POST /chat/skills` 估算 base + prompt + skills 的 token 数，超过 `context_window * 0.3` 时拒绝并提示。

## 问题20的解决方案：索引失败原因结构化（已满足，无需修复）

- 原报告"仅存类名"不实。
- 实际已实现：`documents/indexing.py:509` `_safe_failure_reason` 保存完整 message（前 500 字符）。
- 结论：删除该问题；结构化 category（`parsing_error`/`embedding_error` 等）属增强，P2 可选。

## 问题21的解决方案：OpenAPI 版本化（不实施）

- 版本化与破坏性变更检测服务于不可控外部消费者；本项目前后端同仓库，契约已由 `packages/api-contracts` TS 类型 + 契约测试统一管理，变更会被 CI 立即发现。
- 结论：当前架构不适用，不实施。

## 问题22的解决方案：SSE 断线重连（P2 可选）

- 现状：前端未监听 `EventSource` `onerror` 重连。
- 方案（可选）：前端补 onerror 重连；如需断点续传，后端事件带 `sequence_number` 并支持 `?from_sequence=N`（需短期缓存已发送事件，成本较高）。

## 问题23的解决方案：业务级指标（P2 可选）

- 现状：`/metrics` 已存在（`app.py:396`，暴露 requestCount/failureCount/averageLatencyMs），缺业务指标。
- 方案（可选）：补充 chat 请求数、平均上下文 token、压缩触发次数、MCP 调用延迟等自定义指标。

## 问题24的解决方案：速率限制（P2 可选）

- 现状：无速率限制。
- 方案（可选）：为高成本端点（chat/stream、aiops/diagnose、documents/upload）加 per-user 限流（如 `10/minute`），超限返回 429。本地单用户场景非阻塞，属产品决策。

## 问题25的解决方案：/ready 优雅降级（不实施）

- 依赖粒度健康检查服务于多实例负载均衡摘除；项目为本地单实例（`start-local.sh`），单实例下"全有或全无"语义合理。
- 结论：当前架构不适用，不实施。

## 问题26的解决方案：生产部署文档（P1，文档）

- 现状：`docs/` 只有本地开发文档。
- 方案：新增 `docs/deployment/production.md`，覆盖 Docker Compose 生产模式、Nginx 反代（SSE `proxy_read_timeout`）、SQLite 备份、监控告警接入、日志收集。
- 已完成：新增 `docs/deployment/production.md`——部署形态总览（基础设施容器 + uvicorn/systemd 后端 + Nginx 前端）、Nginx 反代与 SSE 长连接关键配置（`proxy_buffering off`、`proxy_read_timeout 3600s`）、SQLite WAL checkpoint + `.backup` 在线备份与恢复、/health /ready /metrics 监控接入、结构化日志收集、密钥与文件权限（0600）、上线检查清单。
- 已完成：operations-and-monitoring.md 与 README 增加部署文档入口链接。

## 问题27的解决方案：Skill/Prompt 版本控制（不实施）

- 版本回退服务于多人协作审计；项目明确单用户即单租户，用户是唯一修改者，改坏重新编辑即可。
- 结论：等未来多租户/团队场景出现后再评估，当前不实施。

## 问题28的解决方案：测试覆盖率报告（P2 可选）

- 现状：无覆盖率报告与阈值。
- 方案（可选）：CI 增加 `pytest --cov=super_ai --cov-report=term`，设最低阈值（如 70%），低于阈值失败；关键模块（auth、chat、aiops）要求更高。
