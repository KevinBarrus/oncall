# 第四轮解决方案与实施计划

本文件与 `problem4.md` 的编号一一对应。方案以当前源码为事实，未实施项不代表已上线。第四轮无 P0；3 个 P1 均为"前几轮修复叠加后暴露的二阶问题"，修复方向明确、均可局部修复，不需要架构调整。

## 推进顺序

1. 可靠性/正确性（P1）：问题1（证据展开自压缩击穿）、问题3（worker 循环异常防护）、问题2（压缩并发互斥）。
2. 顺手修复（P2，小改动）：问题4（结构化降级标记）、问题5（前端 timed_out 标签）、问题14（spec 漂移）。
3. 安全加固（P2）：问题6（exc_info 脱敏）。
4. 可选/暂缓（P2）：问题7、8、9、10、11、12、13、15。

## 问题1的解决方案：压缩包装跳过自指工具（P1，建议优先）

- 现状：`_wrap_tool_output_compression` 对全部工具套压缩包装，`read_tool_output_evidence` 返回的原文被再次压缩成摘要并生成新 evidenceId，证据展开机制对唯一目标场景失效，且每次展开写入重复 evidence 行。
- 方案：包装循环按名称跳过 `read_tool_output_evidence`（以及 `load_skill` 等内容本身即指令的自指工具）；补充回归测试"调用 read_tool_output_evidence 返回的字符串与 evidence.content 完全相等"。
- 已完成：`_NO_COMPRESSION_TOOL_NAMES` 豁免名单（`read_tool_output_evidence`/`load_skill`），`_wrap_tool_output_compression` 入口直接返回原工具；新增 3 个回归测试（证据展开返回原文、Skill 指令原文保留、普通大输出工具仍被包装）。
- 验证：`uv run pytest -m "not local_config"` = 219 passed（新增 3 个）；ruff/pyright 全绿。

## 问题2的解决方案：压缩路径并发互斥（P1）

- 现状：后台压缩 job handler 与 REST append 路径不持执行租约，与流内 95% 硬限内联压缩可并发；`archive_compacted_messages` 按前缀数量归档，交错时可能抛 RuntimeError 或归档未被摘要覆盖的消息；压缩入队无去重。
- 方案（择一或组合）：
  - job handler 与 REST append 路径复用 `acquire_execution_lease`（与流式对称）；
  - 或 `archive_compacted_messages` 改为按消息 ID 集合 CAS 归档，ID 不匹配即放弃；
  - `_schedule_chat_memory_compaction` 入队前检查同 resource 已有 queued/running job（去重）。
- 已完成（采用 CAS 归档 + 入队去重组合）：`archive_compacted_messages` 接口改为 `message_ids` 集合，SQLite 实现事务内校验 active 前缀 ID 集合与摘要覆盖集合完全一致（append-only 前缀校验成立）才归档，不一致抛 RuntimeError 放弃——消除了"归档未被摘要覆盖的新消息"与"旧摘要覆盖新摘要"；`_schedule_chat_memory_compaction` 默认去重（queued/running 跳过），手动 `memory:compact` 端点 `dedupe=False` 总是入队，mode 切换与 70% 自动触发走去重。
- 说明：未给 REST append / job handler 加执行租约（CAS + 去重已消除错误归档与无谓并发，剩余交错由失败-重试自愈：job 走重试、内联记 last_compaction_error）。
- 已补充测试：CAS 拒绝陈旧 ID 集（内联先归档 + 新消息补齐场景）且不误删新消息、同会话重复入队返回 None。
- 验证：`uv run pytest -m "not local_config"` = 224 passed（新增 2 个）；ruff/pyright 全绿。

## 问题3的解决方案：worker 循环异常防护（P1）

- 现状：`_worker_loop` 裸 while，`_claim_available`/`_execute` 的仓储调用异常会终止 worker task，后台处理静默停摆直到重启。
- 方案：`_worker_loop` 每轮包 try/except，异常时 emit `background.worker.error` 事件并 sleep 退避后继续；`_execute` 的 finally 分支（`mark_*` 失败）同样兜底，只记日志不再向上抛。
- 已完成：`_worker_loop` 双 try/except（claim 与 execute 各一层），失败 emit `background.worker.error`（含 errorCategory + 脱敏 error）+ 指数退避（2/4/8/16/30s 封顶，成功重置）；`_execute` 三个状态记账点（mark_succeeded/mark_cancelled/handle_failure）各自兜底只 emit 事件，`completed/cancelled/failed` 状态事件仅在持久化成功时发出；记账失败后由租约过期 → `claim_next` 自然重取自愈。
- 已补充测试：claim_next 抛错存活、mark_succeeded 抛错存活（job 走租约重取）、handler 异常 + handle_failure 抛错存活——三者均验证 worker 继续处理后续 job。
- 验证：`uv run pytest -m "not local_config"` = 222 passed（新增 3 个）；ruff/pyright 全绿。

## 问题4的解决方案：结构化压缩降级标记（P2，回归：solution3 问题3 部分）

- 现状：仅字符串输出路径在 `_compression` 加 `compressionFailed`；`maybe_compress_structured_tool_output`（知识检索主路径）缺失。
- 方案：结构化路径复用 `tool_output_compression_metadata` 并在 `mode == "sampled_fallback"` 时补 `compressionFailed: True`；补降级路径测试（现有测试用 FakeProvider 不触发降级）。
- 已完成：结构化路径 `_compression` 改为复用 `tool_output_compression_metadata`（与字符串路径一致），sampled_fallback 时补 `compressionFailed: True`；新增回归测试（FailingProvider 触发降级断言标记，另断言 llm_summary 成功路径不带标记）。
- 验证：`uv run pytest -m "not local_config"` = 225 passed（新增 1 个）；ruff/pyright 全绿。

## 问题5的解决方案：前端 timed_out 状态标签（P2，回归：solution3 问题7 配套）

- 现状：契约已含 `timed_out`，后端 SSE 与降级报告已落地，但前端 `asyncStatus.ts` 状态映射表缺失，超时诊断历史显示"状态未知"。
- 方案：`STATUS_DESCRIPTIONS` 增加 `timed_out: { label: "诊断超时", tone: "danger", active: false }`；补前端组件测试。
- 已完成：`asyncStatus.ts` 增加 `timed_out` 条目（label 诊断超时、tone danger、终态）；`chineseWorkspace.test.ts` 补断言。
- 验证：`npm run frontend:typecheck` + `npm run frontend:test` = 82 passed（含新增断言）。

## 问题6的解决方案：异常堆栈文本脱敏（P2，需验证）

- 现状：`SanitizingFormatter` 只脱敏 `record.getMessage()` 渲染文本，`exc_info` 堆栈与 `stack_info` 不经过脱敏；已核实当前 `super_ai` 命名空间无 `logger.exception`/`exc_info` 调用点（潜在缺口非现行泄漏）。
- 方案：`format()` 中对 `formatException(record.exc_info)` 与 `record.stack_info` 拼接结果同样过 `_redact_text`；补含 exc_info 的脱敏测试固化。
- 已完成：`format()` 改为对 `super().format(record)` 的完整结果（含 exc_text/stack_info）再整体过一次 `_redact_text`；新增回归测试（真实 `sys.exc_info()` 堆栈中 `secretKey` 值被脱敏、RuntimeError 保留）。
- 验证：`uv run pytest -m "not local_config"` = 226 passed（新增 1 个）；ruff/pyright 全绿。

## 问题7的解决方案：REST append 端点租约与限流（P2）

- 现状：`POST /chat/sessions/{id}/messages`（非流式）不获取执行租约（与 `:stream` 不对称）、不在限流范围。
- 方案：与问题2 一并处理（复用执行租约）；是否加限流属产品决策（本地单用户低风险）。
- 验证：随问题2 的交错测试覆盖。

## 问题8的解决方案：clear_messages 清理压缩证据（P2）

- 现状：`clear_messages` 只删消息与归档并重置记忆，`compressed_tool_evidence` 与审计行残留且持续增长；evidence 写入无 `source_hash` 去重（会话删除场景已由级联处理，仅清空场景残留）。
- 方案：`clear_messages` 事务内一并删除两表的 session 关联行；evidence 写入按 `(chat_session_id, source_hash)` 去重。
- 验证：清空会话后断言 evidence/审计行计数为 0。

## 问题9的解决方案：后台压缩失败记账（P2）

- 现状：70% 后台 job 失败只进 job 表并退避重试，不写 `last_compaction_error`；与内联路径失败可见性不对称。
- 方案：job handler 捕获异常后调用 `update_memory_state(last_compaction_error=...)`。
- 验证：job 失败后会话 memory API 返回 lastCompactionError。

## 问题10的解决方案：token 计数复用 provider（P2，性能）

- 现状：`count_tokens` 每次调用新建 ChatModel，压缩选段对前缀逐条估算，长会话 O(n²) 放大。
- 方案：provider 缓存 tokenizer/计数器（惰性创建一次），`create_chat_model` 与 token 计数解耦。
- 验证：长历史压缩耗时对比（基准前后）。

## 问题11的解决方案：compacted_message_count 死字段清理（P2）

- 现状：归档表方案落地后该字段恒为 0（archive/clear 均置 0），契约暴露恒 0、前端未用，相关切片/算式误导维护者（并为问题2 的并发算式埋坑）。
- 方案：删字段或明确恒 0 语义并清理相关算式（需迁移与契约同步）。
- 验证：迁移回滚测试覆盖字段删除。

## 问题12的解决方案：evidence 持久化失败不转工具失败（P2）

- 现状：压缩 wrapper 中 `evidence_repository.create` 抛异常直接冒泡，LangChain 记为工具错误，已生成的压缩结果被丢弃。
- 方案：evidence 写入包 try/except，失败仅 emit 事件（metadata 不含 evidenceId，模型仍可使用压缩摘要）。
- 验证：evidence 仓储抛错桩，断言工具调用仍成功返回压缩摘要。

## 问题13的解决方案：流失败持久化 partial 回答（P2，确认项）

- 现状：Agent 事件循环异常时 `answer_parts` 丢弃，用户消息在、回答无；前端有"回答流意外中断"检测。
- 方案（可选）：异常路径若 `answer_parts` 非空，持久化一条带 `interrupted` 标记的 assistant 消息再发 error 事件。
- 说明：属生产体验取舍，当前不实施时应在文档记录。

## 问题14的解决方案：chat-memory 规格与实现对齐（P2，文档）

- 现状：`spec.md` 要求 95% 一律拒绝并手动压缩；实现先内联压缩、失败才拒绝（行为更优但与主规格不一致）；另 `memory.py` docstring 仍写"characters / 4"（已用 tokenizer）。
- 方案：同步 spec.md 的 95% Scenario（改为"先内联压缩，失败才拒绝"）与 docstring（tokenizer 优先 + Unicode 回退）。
- 已完成：主 spec "Context hard limit" 更新为先尝试内联压缩、仍超限/压缩失败才阻止，场景拆为"压缩后拒绝"与"压缩失败拒绝"；同步 `defer-chat-memory-compaction` change 的 MODIFIED 块（含 Thirty-turn 场景名对齐，修复其 archive 校验）；`maybe_compress_tool_output` docstring 改为 tokenizer 优先描述。
- 验证：`openspec validate chat-memory-management --strict` + defer change 通过；docs build 通过。

## 问题15的解决方案：CI 合并测试 + 运维端点边界（P2，确认项）

- 现状：CI 后端 job 对同一套件跑两遍（裸跑 + 带 --cov 重跑）；运维端点（/health、/metrics、/ready、/config/check、/health/mcp）无认证，返回基础设施拓扑与指标（不含密钥值）。
- 方案：CI 合并为一次带 `--cov` 的运行；部署文档明确"运维端点不对外暴露或在 Nginx 层限制来源 IP"。
- 说明：单实例 127.0.0.1 绑定下风险低，属部署边界确认项。
