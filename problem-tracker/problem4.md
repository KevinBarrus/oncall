# 第四轮验收问题

本文件记录生产级验收发现的问题，与 `solution4.md` 中同编号的解决方案对应。

## 验收概要

**验收日期**：2026-08-22
**验收标准**：生产级（正确性、可靠性、安全、可维护性、可测试性、一致性）
**验收方法**：
- ✅ 运行只读验证命令：`uv run ruff check .`（All checks passed）、`uv run pyright`（0 errors, 0 warnings）、`uv run pytest -m "not local_config"`（全部通过；teardown 阶段有 aiosqlite "Event loop is closed" 线程警告，非功能失败）
- ✅ 逐条核对 solution3.md 声明的实现（行号证据见各问题"回归核查"）
- ✅ 深审 jobs/runtime.py、chat/streaming.py、chat/memory.py、memory/sqlite.py、aiops/diagnostics.py、observability.py、auth/service.py、rate_limit.py、tool_registry.py、CI 与 pyproject

**整体结论**：🟡 **基本达标，存在 3 个 P1 可靠性/正确性问题（均集中在第四轮新增/触碰的代码路径）**。第三轮 28 个问题的修复声明经逐条核实**全部真实落地**，其中 2 项存在配套缺口（见问题4、问题5，标注"回归"）。

---

## 问题1：read_tool_output_evidence 工具被自身的压缩包装击穿，永远无法还原原文（P1）

- **位置**：`apps/backend/src/super_ai/chat/streaming.py:683-686`（注册）、`:710-713`（全量包装）、`:778-824`（压缩 wrapper）、`:864-881`（工具实现）
- **现状**：`LangChainChatAgentRunner.stream` 对 `registry.langchain_tools()` 的**全部**工具套 `_wrap_tool_output_compression`，其中包含 `read_tool_output_evidence` 本身（`:683-686` 先注册，`:710-713` 后包装，无排除逻辑）。
- **问题**：证据被持久化的前提是原始输出超过压缩阈值（`memory.py:383-385`，2000 tokens），而 `read_tool_output_evidence` 的返回值就是该原文（`streaming.py:876` `return evidence.content`，str 类型）。wrapper 对 str 结果再次调用 `maybe_compress_tool_output`（`streaming.py:781-783`），原文必然再次超阈值、再次被压缩成摘要并生成新 evidenceId。调用链：模型调用 `read_tool_output_evidence` → wrapper 拦截 → 返回 `[compressed]` 摘要而非原文。**证据展开机制对其唯一目标场景（大输出）完全失效**，工具描述承诺"读取被压缩工具输出的原文"（`streaming.py:880`）无法兑现；且每次展开都会写入一条全量重复的 evidence 行（`streaming.py:790-798`，无 source_hash 去重），放大存储。solution3 问题14 修复了 evidenceId 注入，但展开回路被第三轮的压缩包装（solution2 问题2 的后续实现）破坏，属于两轮修复的交互回归。
- **建议**：包装循环按名称跳过 `read_tool_output_evidence`（以及 `load_skill` 等内容本身即指令的自指工具）；补充回归测试："调用 read_tool_output_evidence 返回的字符串与 evidence.content 完全相等"。

## 问题2：记忆压缩并发互斥缺失，后台压缩任务与内联硬限压缩可并发执行（P1）

- **位置**：`apps/backend/src/super_ai/api/app.py:1796-1822`（压缩 job handler）、`app.py:1255-1281`（REST append 端点）、`chat/memory.py:153-178`（70% 入队 + 95% 内联压缩）、`memory/sqlite.py:443-506`（archive）、`app.py:2190-2204`（无去重入队）
- **现状**：会话流式执行有 15 分钟租约互斥（`chat/streaming.py:184-207`），但两条压缩路径都在租约之外：
  1. `chat_memory_compaction` job handler 读快照后直接 `compact_once`，**不获取也不检查执行租约**（`app.py:1796-1822`）；
  2. REST `POST /chat/sessions/{id}/messages` 在**完全不持租约**的情况下调 `prepare_message`（`app.py:1270-1281`），其中含 95% 硬限内联压缩。
  另外 `_schedule_chat_memory_compaction`（`app.py:2190-2204`）入队无去重——70% 之后每条新消息都会再入队一个压缩 job。
- **问题**：真实调用链——第 N 轮消息在 70% 触发时入队后台压缩（`memory.py:153-154`），任务内 LLM 摘要需数秒；用户紧接着发第 N+1 条消息达到 95% 硬限，流内 `prepare_message` 用新快照内联压缩并 archive（`memory.py:156-163`）。随后后台任务用旧快照的 `message_count` 执行 archive：`sqlite.py:460-474` 按当前 active 表前缀取 `limit(message_count)` 行。守卫 `len(rows) != message_count`（`sqlite.py:473`）只防数量不匹配——常规交错下会抛 RuntimeError 使一方压缩失败（用户看到 `CHAT_CONTEXT_LIMIT_REACHED` 或 job failed）；但在"内联先 archive、随后多条新消息追加、行数恰好补齐"的交错下（无租约的 REST 路径可编程制造），后台任务会**归档未被其摘要覆盖的较新消息并用旧摘要覆盖新摘要**，这批消息从此不在模型上下文也不在记忆中（仅归档表可查）。两个后台 job 之间已被 `max_concurrent_per_kind=1`（`app.py:348`）串行化，但 job↔内联、REST↔流均无互斥。
- **建议**：job handler 与 REST append 路径复用 `acquire_execution_lease`；或将 `archive_compacted_messages` 改为按消息 ID 集合（而非前缀数量）CAS 归档，ID 不匹配即放弃；`_schedule_chat_memory_compaction` 入队前检查同 resource 已有 queued/running job。
- **验证**：并发触发"后台压缩 + 内联压缩"的交错测试，断言归档集合与摘要覆盖集合一致。

## 问题3：后台任务 worker 循环无异常防护，单次 DB 异常永久停摆后台处理（P1）

- **位置**：`apps/backend/src/super_ai/jobs/runtime.py:97-104`（worker loop）、`:133-177`（_execute）
- **现状**：`_worker_loop` 是裸 `while` 循环：`await self._claim_available(worker_id)` 与 `await self._execute(job, worker_id)` 均无 try/except；`start()`（`:80-87`）创建 task 后无人监控其存活，`stop()` 只是收集结果。
- **问题**：`_claim_available` 内的仓储调用（`runtime.py:113-118` `claim_next`）或 `_execute` 内 except/finally 分支中的 `handle_failure`/`mark_succeeded`/`mark_cancelled`（`runtime.py:137-142`、`:150-177`）抛出的任何异常（SQLite busy 超过 `busy_timeout=5s` 的 `OperationalError`、磁盘 I/O 错误等瞬时故障）都会直接冒泡终止该 worker task。后果：**后台处理（记忆压缩、文档索引、AIOps 诊断）静默停摆直到重启进程**，无告警、无事件（异常发生在 emit_event 之外）。本项目为并发写 SQLite 的架构（请求路径 + 2 个 worker），busy 超时是真实可发生的故障模式——这正是 solution3 问题6 加 per-kind 限制想缓解的场景，但限制本身防不住这种单点死亡。注意：handler 执行期内的异常已被 `_execute` 的 `except Exception` 捕获（`:155-170`），问题仅在**框架自身的仓储调用**无防护。
- **建议**：`_worker_loop` 每轮包 try/except，异常时 emit `background.worker.error` 事件并 sleep 退避后继续；`_execute` 的 finally 分支（`mark_*` 失败）同样兜底，只记日志不再向上抛。

---

## 问题4：结构化工具压缩降级缺 compressionFailed 标记（P2，回归：solution3 问题3 部分）

- **位置**：`apps/backend/src/super_ai/chat/memory.py:437-443`（结构化路径）、`chat/streaming.py:786-789`（字符串路径，已有标记）
- **现状**：solution3 问题3 声明"工具压缩降级（sampled_fallback）在 `_compression` metadata 增加 compressionFailed 标记"。核实结果：**仅字符串输出路径实现**（`streaming.py:788-789`）；`maybe_compress_structured_tool_output` 的 `_compression` 只有 mode/sourceHash/originalChars/compressedChars（`memory.py:437-443`），无 compressionFailed。
- **问题**：知识检索工具返回 dict（`retrieval/tool.py`，经 `streaming.py:803-823` 走结构化路径），即最主要工具的 sampled_fallback 降级无法通过审计 `result_summary` 查询到，solution3 声明的可观测目标对主路径落空。两处元数据构造逻辑重复且不一致（`tool_output_compression_metadata` 帮助函数存在但结构化路径未复用）。
- **建议**：结构化路径复用 `tool_output_compression_metadata` 并在 `mode == "sampled_fallback"` 时补 `compressionFailed: True`；补降级路径测试（现有 `test_chat_memory.py:324-342` 用 FakeProvider 不触发降级，未覆盖）。

## 问题5：前端状态映射缺 timed_out，超时诊断显示"状态未知"（P2，回归：solution3 问题7 配套）

- **位置**：`packages/api-contracts/src/sse.ts:71`（契约已含 timed_out）、`apps/frontend/src/ui/asyncStatus.ts:9-27`（状态表缺失）
- **现状**：solution3 问题7 在共享契约为 `TaskStatusSseEvent.status` 增加 `timed_out`，后端 SSE 与降级报告已核实落地（`aiops/diagnostics.py:283-288`，report → task.status(timed_out) → complete 序列完整）。但前端 `STATUS_DESCRIPTIONS` 映射表没有 `timed_out` 条目。
- **问题**：诊断历史列表（`AiopsHistory.vue:21` 经 `AsyncStatusBadge` → `describeAsyncStatus`）与时间线对超时任务渲染"状态未知"（neutral）。流内用户能看到后端附带的消息（"诊断超时，已生成含已收集证据的降级报告"），但历史记录的状态标签错误——三端同步（后端/契约/前端）在最后一环漏了 UI 标签映射。
- **建议**：`asyncStatus.ts` 增加 `timed_out: { label: "诊断超时", tone: "danger", active: false }`；补前端组件测试。

## 问题6：SanitizingFormatter 不脱敏异常堆栈文本（P2，需验证）

- **位置**：`apps/backend/src/super_ai/observability.py:157-161`
- **现状**：`SanitizingFormatter.format` 只对 `record.getMessage()` 的渲染文本做 `_redact_text`，然后 `super().format()` 追加的 `exc_info` 堆栈与 `stack_info` 文本不经过任何脱敏。
- **问题**：若未来任何调用点使用 `logger.exception(...)` / `logger.error(..., exc_info=True)`，异常消息中的敏感值（如含密钥的 URL 或 config repr）将原样进入日志。**已核实当前 `super_ai` 命名空间内无 `logger.exception`/`exc_info` 调用点**（rg 全量扫描为空），故为潜在缺口而非现行泄漏，降级为 P2 需验证项；另注意 uvicorn/langchain 等第三方命名空间日志不受该 formatter 覆盖（solution3 声明范围即"super_ai 命名空间"，与声明一致，不计为回归）。
- **建议**：`format()` 中对 `self.formatException(record.exc_info)` 与 `record.stack_info` 的拼接结果同样过 `_redact_text`；补一条含 exc_info 的脱敏测试固化。

## 问题7：非流式 REST append 端点无租约且不在限流范围内（P2）

- **位置**：`apps/backend/src/super_ai/api/app.py:1255-1306`
- **现状**：`POST /chat/sessions/{id}/messages`（非流式）不获取执行租约（与 `:stream` 端点的租约互斥不对称），也未接入 per-user 限流——限流只覆盖三个高成本端点（`:stream` `app.py:1313-1314`、aiops 诊断创建 `:1391-1392`、文档上传 `:694`）。
- **问题**：并发互斥部分已在问题2 展开（重复触发内联压缩）。限流部分：该端点执行 `prepare_message`（可能触发 LLM 压缩）与消息持久化，可被高频调用消耗 LLM 配额——本地单用户场景下为低风险，属产品决策范畴（solution3 问题24 只接了三个端点），故 P2。
- **建议**：与问题2 一并处理（复用租约）；是否加限流由产品决策。

## 问题8：clear_messages 不清理 compressed_tool_evidence，全量工具原文持续残留（P2）

- **位置**：`apps/backend/src/super_ai/memory/sqlite.py:276-326`（clear_messages）、`streaming.py:790-798`（evidence 写入无去重、无大小上限）
- **现状**：`clear_messages` 只删除 `ChatMessageModel` 与 `ArchivedChatMessageModel` 并重置记忆状态。**已核实 `delete_session`（`sqlite.py:328-352`）无此问题**——`CompressedToolEvidenceModel` 与 `AgentToolCallAuditModel` 对 `chat_sessions.id` 均为 `ondelete="CASCADE"`（`models.py:475/508`、迁移 `202607110012`），且 `foreign_keys=ON`（`database.py:109`），会话删除时级联清理。
- **问题**：清空会话消息后，`compressed_tool_evidence.content`（保存的是**未压缩的完整工具原始输出**，无大小上限）与审计行永久残留且持续增长；每次压缩调用新增一条 evidence 行，无 `source_hash` 去重。违背 AGENTS.md"删除数据库记录时同步处理关联……审计生命周期"的精神（会话仍存活，严格说是"清理"而非"删除"场景）。单用户架构下无跨用户泄露（`get` 强制 owner+session 过滤，`sqlite.py:969-976`），故 P2。
- **建议**：`clear_messages` 事务内一并删除两表的 session 关联行；evidence 写入按 `(chat_session_id, source_hash)` 去重。

## 问题9：后台压缩 job 失败不落 last_compaction_error，两套失败可见性不对称（P2）

- **位置**：`apps/backend/src/super_ai/api/app.py:1796-1822`（handler 无 error 记账）、`chat/memory.py:165-178`（仅内联路径记账）
- **现状**：95% 硬限内联压缩失败会写 `last_compaction_error`/`last_compaction_failed_at`（solution3 问题3 已核实）；70% 触发的后台 job 失败只进 job 表 `error_message` 并退避重试 3 次。
- **问题**：自动压缩连续失败（如 LLM 不可用）时，用户从会话 memory API 看到的 `lastCompactionError` 仍为 null，只能翻后台任务状态；两条路径的失败语义不对称。
- **建议**：job handler 捕获异常后同样调用 `update_memory_state(last_compaction_error=...)`。

## 问题10：count_tokens 每次调用新建 ChatModel，压缩选段 O(n²) 放大（P2，性能）

- **位置**：`apps/backend/src/super_ai/llm/provider.py:101-107`（每次 `create_chat_model()`）、`chat/memory.py:729-765`（`_select_messages_for_compaction` 对前缀逐条调 `estimate_context_tokens`）
- **问题**：长会话压缩时产生数百到数千次模型对象构造 + tokenizer 编码；`prepare_message` 每次发消息也逐条构造。无正确性问题，纯性能损耗，长会话下用户可感知延迟。
- **建议**：provider 缓存 tokenizer/计数器（惰性创建一次），`create_chat_model` 与 token 计数解耦。

## 问题11：compacted_message_count 已成死字段，契约暴露恒为 0（P2）

- **位置**：`memory/sqlite.py:499`（archive 置 0）、`:322`（clear 置 0）；消费点 `chat/memory.py:138/236/267/350` 的切片与加法恒为 no-op；`memory_payload`（`memory.py:562`）向契约暴露恒为 0 的 `compactedMessageCount`（前端未使用）
- **问题**：归档表方案落地后该字段失去语义，但契约字段、切片运算、`message_count` 算式仍保留，误导后续维护者（也给问题2 的并发算式埋了坑）。
- **建议**：删字段或在 archive 语义下明确其恒 0 并清理相关算式（需迁移与契约同步）。

## 问题12：evidence 持久化失败会把成功的工具调用整体转为失败（P2）

- **位置**：`apps/backend/src/super_ai/chat/streaming.py:790-798`、`:815-822`
- **现状**：压缩 wrapper 中 `evidence_repository.create` 抛异常会直接冒泡出 `_compressed_coroutine`，LangChain 记为 `on_tool_error`。
- **问题**：压缩内容已生成却因证据落库失败而丢弃，工具调用被报错；与 LLM 压缩失败→采样回退（`memory.py:395-413`）的尽力而为语义不一致。
- **建议**：evidence 写入包 try/except，失败仅 emit 事件（此时 metadata 不含 evidenceId，模型仍可使用压缩摘要）。

## 问题13：聊天流失败时不持久化已生成的 partial 回答（P2，确认项）

- **位置**：`apps/backend/src/super_ai/chat/streaming.py:399-408`
- **现状**：Agent 事件循环中累积 `answer_parts`，任一异常时只发 `error` SSE 事件并 return，`answer_parts` 丢弃；用户消息已持久化（`:249-256`）。
- **问题**：流中断时前端已逐字符渲染的 partial 回答在刷新后消失（用户消息在、回答无），对话历史出现"有问无答"。前端有"回答流意外中断"检测（solution3 问题22 限制记录），后端不补一条 partial assistant 消息属可辩解的取舍，但生产体验上值得记录。
- **建议**：异常路径若 `answer_parts` 非空，持久化一条带 `interrupted` 标记的 assistant 消息再发 error 事件。

## 问题14：chat-memory 规格与实现漂移（P2，文档）

- **位置**：`openspec/specs/chat-memory-management/spec.md:60-69` vs `chat/memory.py:156-196`
- **现状**：规格要求达到 95% 一律拒绝并要求用户手动压缩；实现是先内联压缩、失败才拒绝。
- **问题**：行为更优但与主规格不一致；AGENTS.md 要求"以可执行代码与测试为事实，并在同一变更中修正文档漂移"。另 `chat/memory.py:377-380` docstring 仍写"characters / 4"估算，实际已用 tokenizer（solution2 修复后未更新注释）。
- **建议**：同步 spec.md 的 95% Scenario 与 docstring。

## 问题15：CI 全量测试跑两遍 + 运维端点无认证（P2，确认项）

- **位置**：`.github/workflows/ci.yml:48-53`（先裸跑 `pytest -m "not local_config"`，再带 `--cov` 全量重跑）；`apps/backend/src/super_ai/api/app.py:396-453`（/health、/metrics、/ready、/config/check、/health/mcp 无 current_user 依赖）
- **现状**：CI 后端 job 对同一套件跑两遍，浪费约一半时间（可合并为一次带 --cov 的运行）。运维端点不要求认证：`/config/check` 返回 provider/model/baseUrl/Milvus uri/collectionName（`app.py:2079-2112`，已核实**不含**密钥值），`/metrics` 返回请求计数。
- **问题**：本机 127.0.0.1 绑定下单实例场景风险很低（单实例架构是明确决策，不计为缺陷）；但部署文档（docs/deployment/production.md）指导用 Nginx 对外提供服务时，若照搬路由配置会暴露基础设施拓扑与指标。属部署边界确认项，非代码缺陷。
- **建议**：CI 合并两个 pytest 步骤；部署文档明确"运维端点不对外暴露或在 Nginx 层限制来源 IP"。

---

## 回归核查结果（solution3.md 逐条）

| solution3 声明 | 结论 | 证据 |
|---|---|---|
| 问题3 last_compaction_error 字段/清除/契约同步 | ✅ 已核实 | 迁移 `202608210001`；`memory.py:165-178` 记账、`:344-352` 清除；`chat.ts:26-27` |
| 问题3 compressionFailed 标记 | ⚠️ 部分（回归） | 仅字符串路径 `streaming.py:788-789`；结构化路径缺失（见问题4） |
| 问题4 audit_failure_count | ✅ 已核实 | `streaming.py:594-601` 递增 + 内层 try/except |
| 问题5 跨轮证据去重 + 行级预算 | ✅ 已核实 | `streaming.py:507-517`（审计去重）、`:529-538`（citation 去重）、`:498-506`（整条丢弃） |
| 问题6 per-kind 并发限制 | ✅ 已核实 | `runtime.py:106-131` + `app.py:343-350`（三种 kind 各限 1） |
| 问题7 AIOps 整图超时 | ✅ 已核实 | `diagnostics.py:150-181`（deadline + wait_for + aclose）、`:218-298`（timed_out 降级报告与 SSE 序列）；前端标签缺口见问题5 |
| 问题8 BM25 缓存主动失效 | ✅ 已核实 | `app.py:2892-2898`（尽力而为失效）+ `retrieval/tool.py:205-213` |
| 问题9 评测 --mock | ✅ 已核实 | `aiops_evaluation.py:280-317/482`、`rag_evaluation.py:1828-1829` |
| 问题10 SanitizingFormatter | ✅ 已核实 | `observability.py:150-173`，接入 `configure_structured_logging`；exc_info 缺口见问题6 |
| 问题12 SQLite 0600 | ✅ 已核实 | `database.py:68-82`；实测 `var/memory.sqlite3` 权限 600 |
| 问题13 错误码三端同步 | ✅ 已核实 | `sync_error_catalog.py` + `ci.yml:44-47` + 双向契约测试 |
| 问题15 迁移回滚测试 | ✅ 已核实 | `test_memory_migrations.py:74/94`（单步 + 全链回滚） |
| 问题19 System Prompt 预算预检 | ✅ 已核实 | `app.py:2660-2708`，三个端点接入（`:995/:1020/:1077`），预算 min(30%, 30000) |
| 问题22 SSE 连接建立重试 | ✅ 已核实 | `apps/frontend/src/api/sseClient.ts:15/65-87`（2 次退避、非 2xx 不重试） |
| 问题23 业务指标 | ✅ 已核实 | `observability.py:83-114` + `app.py:408-422` + `streaming.py:182` 等埋点 |
| 问题24 速率限制 | ✅ 已核实 | `rate_limit.py`（滑动窗口、线程安全）+ 三端点接入 + 429 错误码 |
| 问题26 生产部署文档 | ✅ 已核实 | `docs/deployment/production.md` 存在 |
| 问题28 覆盖率门禁 | ✅ 已核实 | `pyproject.toml:68-73`（fail_under=80）+ `ci.yml:50-53` + `check_coverage.py` |

另核实无误（第三轮曾误报、本轮复查仍达标）：会话执行租约（`streaming.py:184-207` + `sqlite.py:115-151` 原子条件 UPDATE、过期接管、token 校验释放）、evidenceId 注入、MCP 客户端关闭、报告降级、Milvus 作用域过滤、工具同名限定（`tool_registry.py:101-140`）、Argon2 + token 哈希 + 时序均衡登录（`auth/service.py`）。

---

## 问题汇总

### P1（3 个）

1. **问题1**：read_tool_output_evidence 被压缩包装击穿（正确性，证据展开机制失效）
2. **问题2**：记忆压缩并发互斥缺失（可靠性/正确性，job↔内联、REST↔流无互斥）
3. **问题3**：worker 循环无异常防护（可靠性，单次 DB 异常永久停摆后台处理）

### P2（12 个）

问题4（回归：solution3 问题3 部分）、问题5（回归：solution3 问题7 配套）、问题6（需验证）、问题7、问题8、问题9、问题10、问题11、问题12、问题13（确认项）、问题14、问题15（确认项）

### P0

无。三个 P1 均为已核实调用链的真实缺陷，但不构成"启动即坏/不可恢复数据丢失/安全边界突破"级别的阻塞项。

---

## 逐模块验收结论

| 模块 | 评定 | 说明 |
|------|------|------|
| 1. 后端工程与 API | ✅ 通过 | 渐进拆分推进中（auth 域已示范）；envelope/错误码三端同步、限流、request id 均核实达标 |
| 2. Agent 主循环（聊天） | 🟡 存疑 | 租约/审计/事件翻译达标；read_tool_output_evidence 自压缩（问题1）与 partial 不持久化（问题13） |
| 3. AIOps 诊断 | ✅ 通过 | 整图超时、timed_out 降级报告、SSE 序列、错误路径全部核实；前端标签缺口记问题5 |
| 4. 上下文/记忆管理 | 🟡 存疑 | 三模式/预算/归档/忠实性校验达标；压缩并发互斥缺失（问题2） |
| 5. 压缩策略 | 🟡 存疑 | 工具压缩链路与降级完整，但 evidence 还原失效（问题1）、结构化降级标记缺失（问题4） |
| 6. Skill 与 Prompt 管理 | ✅ 通过 | 上传校验、64KB、预算预检（三端点）核实达标 |
| 7. 工具系统（Registry/MCP） | ✅ 通过 | 同名限定、provider 路由、MCP 关闭/复用核实达标 |
| 8. RAG 与知识检索 | ✅ 通过 | BM25 失效接入删除路径、作用域过滤与转义测试在位、无命中不编造 |
| 9. durable job runtime | 🔴 不通过 | worker 循环脆弱（问题3）；租约/心跳/重试/退避/per-kind 限制本身实现正确 |
| 10. 评测、CI 与工程质量 | ✅ 通过 | ruff/pyright/pytest 全绿、覆盖率门禁、mock 评测、错误码同步检查在位；CI 重复跑测试记问题15 |
| 11. 代码质量与安全 | ✅ 通过 | strict pyright 0 错、Argon2/token 哈希、脱敏双路径达标；exc_info 缺口记问题6 |

## 最终验收结论

**生产就绪度**：🟡 **基本达标，存在 3 个 P1**。第三轮全部修复声明经逐条核实真实落地（其中问题3/问题7 的配套存在两处小回归）；新发现的 3 个 P1 集中在"压缩包装 × 证据展开"的交互回归、压缩路径的租约盲区、以及 job runtime 框架自身的异常脆弱性——都是前几轮修复叠加后暴露的二阶问题，修复方向明确且均可局部修复，不需要架构调整。
