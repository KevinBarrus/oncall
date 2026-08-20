# 第三轮验收问题

本文件记录生产级验收发现的问题，与 `solution3.md` 中同编号的解决方案对应。

> **修正说明**：本文件已根据复核结果（`problem3-feedback.md` 用户逐条核对 + `problem3-correction.md` 原验收方修正）重写。原报告将多个"存疑未验证"直接标为 P0，并因搜索方法名错误产生误报；修正后为 **0 个 P0、4 个 P1**。每条问题标注核实后的真实状态。

---

## 验收概要（修正后）

**验收日期**：2026-08-20  
**验收标准**：生产级（正确性、可靠性、安全、可维护性、可测试性、一致性）  
**验收方法**：
- ✅ 运行只读验证命令：`uv run ruff check .`（通过）、`uv run pyright`（0 errors）、`uv run pytest -m "not local_config"`（182 个测试全通过）
- ✅ 逐条核对关键代码路径（会话租约、Skill 校验、evidenceId 注入、MCP 关闭、报告降级、索引失败原因等）
- ✅ 检查 CI 配置、依赖管理、安全与权限边界

**整体结论（修正后）**：🟢 **基本达标，存在 4 个 P1 改善项**

**第二轮修复状态（修正后）**：28 个问题全部修复，无回归

---

## 问题1：app.py 仍是 2788 行"上帝文件"（P2，非阻塞）

- **位置**：`apps/backend/src/super_ai/api/app.py`
- **现状**：约 53 个路由、148 个函数仍集中在一个文件；只拆分了 auth 域到 `api/routers/auth.py`
- **问题**：单一职责不足，文件过大影响可维护性
- **核实**：原报告标为"P0 阻塞 + 回归"不成立——渐进拆分是 solution2.md 问题20 的明确决策（已建 `api/dependencies.py` + `api/routers/` 模式），属设计的渐进推进，非缺陷
- **建议**：维持"新增或修改路由时优先迁移"原则；任一域发生路由变更时同步迁移该域全部路由，不一次性重写

## 问题2：会话执行租约（已实现，无需修复）

- **状态**：原报告误报（搜索方法名 `acquire_chat_session_lease` 错误，实际为 `acquire_execution_lease`）
- **核实结果**：`chat/streaming.py:183` 获取 15 分钟租约、`:191-193` 冲突返回 `CHAT_SESSION_BUSY`、`:204-206` finally 释放，与 solution2.md 问题13 一致，已正确实现

## 问题3：压缩失败降级未持久化失败原因（P2 可选）

- **位置**：`chat/memory.py:324-344`、`chat/memory.py:390-402`
- **现状**：压缩失败保留旧状态、发出 `chat.tool_compression.fallback` 事件，但失败原因只写结构化日志，未持久化到可查询表
- **问题**：用户无法从 API 得知"上次自动压缩为何失败"，无法统计哪些工具输出经常压缩失败
- **建议**：会话表增加 `last_compaction_error`/`last_compaction_failed_at`，或审计记录加 `compression_failed` 标记

## 问题4：MCP 工具调用审计失败不可查询（P2 可选）

- **位置**：`chat/streaming.py:524-560`
- **现状**：`_persist_tool_call_audit` 失败只 emit `chat.tool_audit.failed` 事件，聊天继续
- **问题**：审计失败不阻断流程、无告警，事后无法知道哪些工具调用丢失了审计
- **建议**：assistant 消息 metadata 写 `auditFailed` 标记，或会话级累积 `audit_failure_count` 并在会话 API 返回

## 问题5：跨轮工具证据注入无去重、截断策略不明确（P2 可选）

- **位置**：`chat/streaming.py:480-522`
- **现状**：`_build_cross_turn_context()` 取最近 6 条审计 + 8 个 citation，按 4000 字符直接截断，未去重
- **问题**：同一证据可能重复注入浪费预算；字符截断可能截到 citation 一半
- **建议**：按 ID 去重；改用 token-aware 整条丢弃式截断

## 问题6：后台任务无全局并发限制（P1，建议优先）

- **位置**：`apps/backend/src/super_ai/jobs/runtime.py`
- **现状**：无 semaphore/max_concurrent
- **问题**：批量任务（记忆压缩、文档索引）可能同时写 SQLite 触发 `SQLITE_BUSY`，或打满 LLM/Milvus 配额
- **建议**：worker 增加 `max_concurrent_tasks`（默认 5），达到上限等待；或按任务类型分别限流

## 问题7：AIOps 诊断无整图 wall-clock 超时（P1，建议优先）

- **位置**：`apps/backend/src/super_ai/aiops/diagnostics.py`
- **现状**：LangGraph 图运行处无整体超时
- **问题**：LLM 卡住（模型 overload、网络抖动）会长期占用后台任务槽位，用户看到"执行中"无法判断是否卡死
- **建议**：整图执行加 `asyncio.timeout(600)`；超时生成降级报告并标记任务 `timed_out`，SSE 发送 `timeout` 事件

## 问题8：知识库删除未清理 BM25 缓存（P2 可选）

- **位置**：`retrieval/tool.py:311-329`
- **现状**：`_keyword_corpora` 60s TTL，缓存键 `(owner_user_id, knowledge_base_ids)`
- **问题**：文档删除后 60s 窗口内检索可能命中已删除文档的 corpus
- **建议**：文档删除/索引完成时主动失效缓存，或缓存键加入知识库版本号

## 问题9：评测脚本依赖外部 API 无 mock 回退（P2 可选）

- **位置**：`tests/aiops_evaluation.py:28`、`tests/rag_evaluation.py:28`
- **现状**：评测读取 `AIOPS_EVAL_API_BASE_URL`/`RAG_API_BASE_URL`，端到端评测只能本地/定时跑
- **问题**：本地没起后端时无法离线验证评测逻辑
- **建议**：提供 mock fixture（3-5 案例），评测脚本加 `--mock` 参数，CI 跑 mock 评测

## 问题10：非结构化日志脱敏不完整（P1，安全加固）

- **位置**：`apps/backend/src/super_ai/observability.py`、日志输出点
- **现状**：`emit_event` 已用 `_redact` 脱敏（覆盖 `_key`/`_secret`/`_token` 后缀），但 `logger.info/exception` 等直接调用不受保护
- **问题**：FastAPI 中间件、MCP 初始化、后台任务抛异常时可能把含密钥的 config 打印到日志
- **建议**：增加全局日志 Formatter/Filter 统一脱敏；补充测试"日志输出不含真实密钥"

## 问题11：Skill 上传校验（已实现，无需修复）

- **状态**：原报告误报
- **核实结果**：`chat/configuration.py:91` `validate_skill_upload` 已校验文件名严格 `SKILL.md`、64KB 大小限制（`MAX_CHAT_SKILL_BYTES`）、UTF-8 解码、YAML frontmatter（name/description）。恶意指令注入属 LLM 二道校验范畴，成本高，不实施

## 问题12：SQLite 文件权限未限制（P2 可选）

- **位置**：`apps/backend/var/memory.sqlite3`
- **现状**：文件权限由 umask 决定
- **问题**：共享服务器上权限可能过宽（644），数据库含密码哈希、聊天历史
- **建议**：启动时显式限制文件权限（如 0600）；部署文档补充生产建议

## 问题13：前端错误码类型与后端 error_catalog 手动同步（P2 可选）

- **位置**：`packages/api-contracts/src/errors.ts:9-70`、`error_catalog.py`
- **现状**：两处为同一套错误码的双份定义，现有契约测试只测形状不测跨端一致性
- **问题**：新增错误码需手动同步，容易漏改
- **建议**：补契约测试断言后端 `/openapi.json` 错误响应与 `errors.ts` 一致

## 问题14：工具输出压缩 evidenceId（已实现，无需修复）

- **状态**：原报告误报（自行标注"需验证"但未验证）
- **核实结果**：`chat/streaming.py:769/793` 注入 `metadata["evidenceId"]`、`:658` 注册 `read_tool_output_evidence` 工具、`:835-851` 工具实现完整

## 问题15：Alembic 迁移未测试回滚路径（P2 可选）

- **位置**：`apps/backend/alembic/versions/`
- **现状**：downgrade 未被测试
- **问题**：含数据转换的迁移回滚可能丢数据；SQLite 部分 ALTER 受限
- **建议**：CI 增加 `upgrade head && downgrade -1 && upgrade head`；单向迁移明确 `raise NotImplementedError` 并注明

## 问题16：MCP 连接配置变更关闭旧客户端（已实现，无需修复）

- **状态**：原报告误报
- **核实结果**：`mcp_connections.py:156` 配置替换时 `aclose()`、`:176` 应用关闭时清理、`:181-185` 统一 `aclose()`，已正确实现

## 问题17：向量存储 tenant_id 作用域过滤（P2，确认项）

- **位置**：`apps/backend/src/super_ai/vector_store/milvus.py`
- **现状**：`search_chunks`/`list_chunks`/`delete_document_chunks` 全部强制显式 `tenant_id` + 知识库作用域参数，无 `count_chunks` 独立操作
- **核实**：原报告标 P0，复核未找到实际缺口；降级为确认项
- **建议**：补充"跨租户查询返回空"测试固化边界；未来新增 Milvus 操作必须沿用显式作用域参数

## 问题18：诊断报告生成降级（已实现，无需修复）

- **状态**：原报告误报
- **核实结果**：`diagnostics.py:899` `_fallback_report_content`、`:1367` 完整降级报告逻辑，已正确实现

## 问题19：System Prompt 注入未预检长度（P2 可选）

- **位置**：`api/app.py`（system prompt 组装）、`chat/configuration.py`
- **现状**：用户 Prompt + 多个 Skill 全文（`load_skill` 后）可能超出上下文窗口，首次对话才暴露
- **建议**：Prompt/Skill 持久化时估算组装后 token 数，超过 `context_window * 0.3` 拒绝并提示

## 问题20：文档索引失败原因（已满足，无需修复）

- **状态**：原报告"仅存类名"不实
- **核实结果**：`documents/indexing.py:509` `_safe_failure_reason` 保存完整 message（前 500 字符）。结构化 category（`parsing_error`/`embedding_error` 等）属增强，P2 可选

## 问题21：OpenAPI 版本化（不实施）

- 版本化与破坏性变更检测服务于不可控外部消费者；本项目前后端同仓库，契约已由 `packages/api-contracts` TS 类型 + 契约测试统一管理
- 结论：当前架构不适用

## 问题22：SSE 断线重连（P2 可选）

- **位置**：`apps/frontend/src/` SSE client
- **现状**：未监听 `EventSource` `onerror` 重连
- **建议**：前端补 onerror 重连；断点续传（`sequence_number` + `?from_sequence=N`）成本较高，可选

## 问题23：业务级 Prometheus 指标（P2 可选）

- **位置**：`api/app.py:396`（`/metrics`）
- **现状**：`/metrics` 已存在，暴露 requestCount/failureCount/averageLatencyMs；缺业务指标
- **核实**：原报告称"未检查实现"，实际已实现基础请求指标
- **建议**：补充 chat 请求数、平均上下文 token、压缩触发次数、MCP 调用延迟等

## 问题24：缺少速率限制（P2 可选）

- **位置**：全部 API 端点
- **现状**：无用户级速率限制
- **问题**：恶意用户可快速耗尽 LLM 配额或后台队列（本地单用户场景非阻塞，属产品决策）
- **建议**：高成本端点（chat/stream、aiops/diagnose、documents/upload）加 per-user 限流，超限返回 429

## 问题25：/ready 健康检查优雅降级（不实施）

- 依赖粒度健康检查服务于多实例负载均衡摘除；项目为本地单实例（`start-local.sh`），单实例下"全有或全无"语义合理
- 结论：当前架构不适用

## 问题26：缺少生产部署文档（P1，文档）

- **位置**：`docs/`
- **现状**：只有本地开发文档
- **建议**：新增 `docs/deployment/production.md`，覆盖 Docker Compose 生产模式、Nginx 反代（SSE `proxy_read_timeout`）、SQLite 备份、监控告警、日志收集

## 问题27：Skill/Prompt 无版本控制（不实施）

- 版本回退服务于多人协作审计；项目明确单用户即单租户，用户是唯一修改者，改坏重新编辑即可
- 结论：等未来多租户/团队场景出现后再评估

## 问题28：测试覆盖率未量化（P2 可选）

- **位置**：全测试套件
- **现状**：无覆盖率报告与阈值
- **建议**：CI 增加 `pytest --cov=super_ai --cov-report=term`，设最低阈值（如 70%），低于阈值失败

---

## 修正后的问题汇总

### P1（建议优先处理，4 个）

1. **问题7**：AIOps 整图 wall-clock 超时（可靠性，与诊断链路直接相关）
2. **问题6**：后台任务全局并发限制（可靠性，SQLITE_BUSY 风险）
3. **问题10**：非结构化日志脱敏加固（安全）
4. **问题26**：生产部署文档（运维）

### P2（可选改善，15 个）

问题3、4、5、8、9、12、13、15、17（确认项）、19、22、23、24、28，以及问题1（拆分推进）

### 已实现，无需修复（6 个）

问题2、11、14、16、18、20

### 不实施（3 个）

问题21（OpenAPI 版本化）、25（/ready 降级）、27（版本控制）——为不存在的场景预支复杂度

---

## 逐模块验收结论（修正后）

| 模块 | 评定 | 说明 |
|------|------|------|
| 1. 后端工程与 API | ✅ 通过 | 渐进拆分是设计决策，非缺陷 |
| 2. Agent 主循环 | ✅ 通过 | 会话租约已实现，非回归 |
| 3. 上下文/记忆管理 | ✅ 通过 | 核心功能完整 |
| 4. 压缩策略 | ✅ 通过 | 降级机制已实现 |
| 5. Skill 与 Prompt | ✅ 通过 | 上传校验完整 |
| 6. 工具系统 | ✅ 通过 | MCP 复用、隔离、关闭均已实现 |
| 7. RAG 与知识检索 | ✅ 通过 | tenant 作用域过滤未发现缺口 |
| 8. 评测与 CI | ✅ 通过 | 门禁完整 |
| 9. 代码质量与安全 | 🟡 存疑 | 日志脱敏可加固（P1） |

## 最终验收结论（修正后）

**生产就绪度**：🟢 **基本达标，存在 4 个 P1 改善项**（AIOps 超时、任务并发限制、日志脱敏加固、部署文档）。核心架构、隔离边界与既有 28 个第二轮问题修复均验证有效。
