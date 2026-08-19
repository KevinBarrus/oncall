# 第二轮评估问题

本文件记录第二轮评估发现的全部问题。每个问题与 `solution2.md` 中同编号的解决方案对应。本轮以生产级标准重新审视系统，重点关注压缩策略、评测方式、记忆管理、工具管理和后端工程五个维度。

## 问题1：token 估算与真实 tokenizer 脱节

`chat/memory.py:473` 的 `estimate_context_tokens` 与 `chat/memory.py:337` 的工具输出压缩都依赖 `langchain_core.messages.utils.count_tokens_approximately` 或 `len(text)//4`，属于启发式估算而非真实分词器计数。对中文日志这一本项目核心场景误差尤其大：`//4` 按"4 字符≈1 token"估，但中文约 1.5 字符/token，会系统性低估中文工具输出体积，导致该压缩时不压缩。整个"context 70% 自动压缩"阈值建立在不准的基数上，无法对生产环境的上下文窗口做出可靠承诺。

## 问题2：工具输出压缩不可逆、丢失关键证据

`chat/memory.py:324-362` 的 `maybe_compress_tool_output` 用 LLM 把超阈值输出"总结"掉，原内容不再回传模型（只保留 `sourceHash`）。对 AIOps 场景，压缩日志可能恰好丢掉那一条决定性 error line，而 Agent 无法再取回原文，缺少"按需展开/重取"机制。`_select_text_for_compression` 尽力保留 signal 行，但最终 LLM 总结是有损且单向的。生产级做法应保留原文引用并允许模型二次拉取，或对关键字段做无损结构化保留。

## 问题3：压缩在请求路径同步阻塞、失败会中断请求

`chat/memory.py:115-176` 的 `prepare_message` 在开始流式响应之前同步调用 `_compact_messages`（内部 `ainvoke` 一次 LLM）。触发压缩时，用户要先等一整轮 LLM 摘要往返才看到任何输出；若模型返回非法 JSON，`chat/memory.py:291-292` 直接 `raise RuntimeError`，把用户这一轮发消息整个打断，没有降级（如"本次跳过压缩，继续用原始上下文"）。

## 问题4：manual 模式切换触发全量串行压缩

`chat/memory.py:198-219` 的 `set_mode` 切到 manual 会立即调用 `compact()`，而 `compact()`（227-258 行）用 `while` 循环把全部未压缩历史一段一段串行 LLM 摘要。长会话切模式等于 N 次串行 LLM 调用阻塞请求。

## 问题5：跨轮上下文不完整

`chat/streaming.py:603-607` 发给模型的历史只保留 `{"role","content"}`，且 `estimate_context_tokens`（`chat/memory.py:482-486`）也只统计 `user/assistant` 消息。上一轮的工具调用与工具返回结果不会在下一轮重放给模型，citation 只存在 assistant 消息的 metadata 里、不注入 content。对"跨轮排障"场景，模型既看不到自己之前的证据，压缩后连原话也只剩摘要，证据链被双重丢弃。

## 问题6：评测不是自动化回归门禁

`tests/ragas_evaluation.py` 需要外部 API key（SiliconFlow、DeepSeek）、运行中的 Milvus 和后端才能跑，仓库没有任何 `.github/workflows`。`TestRagasEvaluation`（`ragas_evaluation.py:1388`）里的 pytest 只测 token overlap、score 解析、MRR 等辅助函数，不测真实检索质量。所谓"评测"没有进入任何自动门禁。

## 问题7：AIOps 诊断链路零量化评测

评测只覆盖 RAG 问答的检索+生成。项目真正的差异化能力——Plan-Execute-Replan 诊断质量、SOP 贝叶斯信念更新是否真的让诊断更准——没有任何端到端量化评测，只有 `sop_belief.py` 的单元测试和诊断管线的 plumbing 测试。无法回答"这个 Agent 诊断对了几次、根因命中率多少"这一生产最关心的问题。

## 问题8："RAGAS"名不副实且是死依赖

`ragas_evaluation.py` 手写了 CP/CR/F/AR 全部指标（直接 prompt LLM），从不 import `ragas`；但 `pyproject.toml:27` 把 `ragas>=0.4.3` 列为运行时依赖。名字、依赖、实现三者不一致。

## 问题9：人工标注的相关性信号脆弱

`_manual_relevance_labels`（`ragas_evaluation.py:403`）用 `_normalise_evidence` 做去空白后的精确子串匹配来判断 chunk 是否相关。改写（paraphrase）后的事实匹配不上会被判 0 分；gold source 只有 3 篇文档，规模是 demo 级。

## 问题10：LLM-as-judge 跨模型裁判与纯数字解析

judge 用 DeepSeek（`ragas_evaluation.py:839`）评 Qwen 生成的内容，跨模型裁判引入系统性偏差；`_parse_score`（`ragas_evaluation.py:477`）只接受 `re.fullmatch` 的纯数字，judge 输出带解释即判无效（保守但会抬高 judge failure rate）；单次打分、无置信区间、无多次运行的方差。

## 问题11：CAG 对比基线是研究性代码混进工程仓

`tests/cag_runner.py` 直接手写 KV Cache、`torch.serialization.add_safe_globals`、bitsandbytes 4bit，依赖 `transformers 5.x` 内部 API（`DynamicLayer`）。作为评测基线可以，但它把 torch/transformers/bitsandbytes 这些重依赖逼进了主依赖。

## 问题12：SQLite 未配置 WAL 与 busy_timeout

`memory/database.py:41-52` 的 `create_memory_engine` 直接 `create_async_engine(url, echo=echo)`，没有 `connect_args={"timeout": ...}`、没有 `PRAGMA journal_mode=WAL`、没有 `foreign_keys`。而系统里 chat、诊断、后台 job runtime 是多协程并发写同一个库的，默认 rollback-journal 下并发写会抛 `database is locked`。设计文档承认"SQLite 并发写入的处理边界"，但引擎层没落地。

## 问题13：会话锁是进程内 WeakValueDictionary、多 worker 失效

`chat/streaming.py:58` 的 `_SESSION_LOCKS` 是 `weakref.WeakValueDictionary`，注释自己写了"one-process lock map; use a database CAS when workers share sessions"。单 uvicorn worker 可用，但一旦 `--workers N` 或起多个进程，同会话并发请求会交错写消息。生产级需要 DB 级锁或 advisory lock。

## 问题14："不删历史"导致无界增长

压缩只推进 `compacted_message_count` 指针，`list_messages` 每次返回全量历史，`_compact_messages` 又把所有未压缩消息拼进 transcript。没有归档/淘汰策略，长期运行的会话 DB 与内存占用单调上涨。

## 问题15：压缩摘要语义无校验

`_validated_memory_document`（`chat/memory.py:555`）只校验 JSON 结构、summary 长度 ≤1200、sourceMessageIds 归属，不校验摘要内容是否忠实。模型把关键结论总结错了，系统无法察觉。

## 问题16：每次对话、每次工具调用都重建 MCP 会话

`chat/streaming.py:564-596`：每个 chat 请求 new 一个 `ToolRegistry`，有 MCP 时 `register_mcp` → `discover_tools`，而 `mcp_client.py:106-122` 的 `discover_tools` 会对每个连接 `sse_client` + `session.initialize()` + `list_tools()`，每条消息都做一次完整 MCP 握手。`mcp_client.py:158-235` 的 `_call_tool` → `_run_sse` 每次工具调用都开新的 `sse_client` + `ClientSession`，一次诊断跑 5 个工具就开 5 个 MCP 连接。无连接池、无缓存、无复用，延迟与资源开销随工具调用次数线性放大。

## 问题17：多连接场景"一坏全挂"

`discover_tools` 里任一 connection 失败即整体抛错；`client_for_user`（`mcp_connections.py:157`）返回所有 enabled 连接，一个坏连接会让整次 `register_mcp` 失败，而不是隔离降级。

## 问题18：同名工具改名而非冲突拒绝

`tool_registry.py:119-126` 撞名时 `_qualified_name` 拼成 `mcp__server__tool`，但没有同步更新工具的 description，模型要靠猜才知道该用哪个限定名。

## 问题19：审计与压缩失败被静默吞掉

`chat/streaming.py:500` 的 `_persist_tool_call_audit` 整段 `except Exception: return`，审计落库失败零感知；`chat/memory.py:351-357` 压缩的 LLM 异常 `except Exception: pass`，静默降级。一个号称"工具调用可审计"的系统，审计本身失败却不可见。

## 问题20：api/app.py 是 2796 行的"上帝文件"

全部约 60 个路由、所有依赖提供者、所有 payload 序列化函数都堆在一个文件里，没有任何 `APIRouter` 拆分。这直接违反项目自己在 `CLAIM.md`/`AGENTS.md` 里写的"职责单一、禁止一个文件包含过多代码"原则。生产级 FastAPI 应按 domain（auth/chat/knowledge/aiops/mcp）拆 router。

## 问题21：重 ML 依赖被错误放进运行时依赖

`pyproject.toml` 的 `dependencies` 含 `torch`、`transformers`、`bitsandbytes`、`accelerate`、`ragas`，但 `apps/backend/src` 零 import（已 grep 确认），只有 `tests/cag_runner.py`、`tests/ragas_evaluation.py` 用。生产安装/`uv sync` 要拉几个 GB 的 torch 生态，只为了跑一个手工评测。应挪到独立的 eval dependency-group。

## 问题22：无 CI/CD

没有 `.github/workflows`。lint/typecheck/test 全靠 README/AGENTS.md 里的手工命令。对一个要求"生产级"的仓，缺自动化门禁是系统性风险。

## 问题23：Replanner 是确定性 switch、不是 LLM 重规划

`aiops/diagnostics.py:729-757` 的 `_determine_contract` 是 4 条 if/else 规则；`_replanner` 节点（667-727 行）只调它来二选一 "executor/report"，不调用 LLM 重新审视计划与证据。"autonomous_replan" 契约也只是强制回退到一次 `knowledge_retrieval`，不是真正基于证据的重规划。这与 README/MISSION 里"Planner→Executor→Replanner→Report、Replanner 决定继续/调整/生成报告"的表述有明显落差。

## 问题24：结构化输出靠 regex 解析、未用 structured output/JSON mode

`_validated_plan_with_sop_ids`（`aiops/diagnostics.py:1072`）用 `re.search(r"\{.*\}", ...)` 从自由文本里抠 JSON，`_clean_markdown_report` 也靠 regex；记忆压缩靠"请只输出 JSON"+ 手工 `json.loads`。生产级应走 `with_structured_output` / JSON schema / function calling，避免贪婪正则抓错范围。

## 问题25：/ready 每次探活打一次付费 LLM

`llm/provider.py:104-126` 的 `check_readiness` 每次 `model.ainvoke("Return exactly: ready")`。负载均衡器每几秒探一次 `/ready` 等于持续扣费 + 探活延迟被 LLM 往返主导。应加 TTL 缓存。

## 问题26：BM25 与向量 list_chunks 每次查询全量扫描

`retrieval/tool.py:298-323` 的 `_keyword_recall` 每次对全部 chunk 重新分词+BM25 打分（无持久索引/增量更新）；`milvus.py:298-325` 的 `list_chunks` 用 `limit=-1` 全量拉取。知识库稍大即 O(N) 扫描，不可扩展。

## 问题27：tenant_id 与 owner_user_id 恒等、租户未真正实现

全仓 `tenant_id=owner_user_id` 传参（如 `sop_belief.py`、`diagnostics.py`）。存在"tenant"概念与字段，但实际是单用户模型，多租户并未真正实现。属"预留了复杂度但没兑现"。

## 问题28：版本约束松、依赖 bleeding-edge

`langchain>=1.3.12` 无上限，`create_agent` API 在 LangChain 1.x 不稳定；`transformers>=5.14.1`、`torch>=2.13.0` 依赖未稳定的新大版本，`cag_runner.py` 注释里"transformers 5.x / DynamicLayer"是踩在 API 边缘上。没有 lock 到确定性版本，`uv sync` 有漂移风险。
