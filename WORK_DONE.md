# Oncall Agent 项目改造记录（非 CAG 部分）

本文档记录对 oncall 项目进行的改造工作，不包括 CAG 模型部署部分（由另一个 Agent 完成，见 `apps/backend/tests/data/CAG_HANDOFF.md`）。

---

## 改造总览

| 序号 | 改造项 | 文件 | 代码量 |
|------|--------|------|--------|
| — | RAG 多策略评测框架 | `tests/ragas_evaluation.py` 等 | ~1100 行 |
| — | 工具输出压缩 | `src/super_ai/chat/memory.py` | ~60 行 |
| — | 文档读取工具 | `src/super_ai/retrieval/read_document_tool.py` | ~80 行 |
| — | 暗色模式 | 前端 14 个文件 | ~200 行 |
| Task 2 | LoopX Interaction Contract | `src/super_ai/aiops/diagnostics.py` | ~95 行 |
| Task 3 | Bayesian SOP Evolution | `src/super_ai/aiops/sop_belief.py`（新）+ `diagnostics.py` | ~290 行 |

---

## 一、RAG 多策略评测框架

### 文件位置

```
apps/backend/tests/
├── ragas_evaluation.py          # 评测主脚本 (~1100 行)
├── data/
│   ├── ragas_test_qa.json       # 15 条 QA 评估集
│   ├── team-alert-response-spec.md   # 公司文档：告警规范 v2.7
│   ├── service-topology.md           # 公司文档：服务拓扑与依赖
│   ├── incident-postmortems.md       # 公司文档：历史故障复盘
│   └── eval_results/                # 评测结果（JSON，gitignored）
└── .env.test                    # API Key（gitignored）
```

### 做了什么

1. **5 种检索策略对比**：
   - `vector-only`：纯 Milvus 向量检索
   - `bm25-only`：纯 BM25 关键词检索
   - `hybrid`：向量 + BM25 并行召回 → RRF 融合
   - `hybrid+rerank`：hybrid → SiliconFlow BGE-reranker-v2-m3 精排
   - `cag-kvcache`：CAG 全量上下文（由另一个 Agent 新增）

2. **双轨指标体系**：
   - LLM-as-Judge（DeepSeek-chat）：Context Precision@5、CP@3、Context Recall、Faithfulness、Answer Relevancy
   - 确定性指标（jieba token overlap）：MRR、NDCG@5、Recall@5

3. **Clean-room baseline**：将 ground truth 直接注入上下文，测量生成质量上界

4. **6 类错误分类**：`data-gap` / `chunking` / `ranking` / `generation` / `attribution` / `partial-hit`

5. **3 篇公司上下文文档**：
   - 告警响应规范 v2.7：P0-P3 等级定义、服务阈值、值班排班、升级规则、聚合抑制、SOP 模板
   - 服务拓扑：微服务架构、依赖路径、DB 配置（max_connections=300/400）、已知脆弱点
   - 历史故障复盘：INC-2026-0715（api-gateway 超时）、INC-2026-0618（Redis 击穿）、INC-2026-0522（user-db 主从延迟）

6. **15 道分层 QA**：8 道 KB 依赖（答案全在文档中）+ 4 道 KB 辅助（文档有帮助但不完整）+ 3 道 KB 无覆盖（测拒答/诚实度）

### 评测迭代中解决的问题

**第一轮**：初始评测用通用技术文档 + 通用 QA。结果 CP=0.20-0.26，10 data-gap + 5 unknown。

→ 根因：文档是公开知识，LLM 不看文档也能回答，无法区分 RAG 检索 vs LLM 自身记忆。

→ 修复：换用公司专属文档 + 重写 QA 为 8+4+3 分布 + 改 Prompt 为双来源标注（📄/💡）。

**第二轮**：新文档跑出来仍是 12 unknown，CP=0.35，MRR=0.59。

→ 深入分析发现三个问题：

1. **token overlap 对中文无效**：`str.split()` 把 "服务分级与告警阈值" 当成一个 token，MRR/NDCG/R@5 全部废掉

2. **CP@5 在 small-KB 场景不公平**：KB 只有 3 篇文档，大多数问题最多命中 2-3 个 chunk，后 2 个噪音 chunk 强制拉低 CP

3. **错误分类逻辑缺陷**：大量"部分成功"的题掉进 `unknown` 兜底分支

→ 修复：
- 引入 **jieba 分词**，替换所有 `.split()` 调用，token overlap 阈值从 0.08 调至 0.15
- 新增 **CP@3 指标**（仅取 top-3 chunk 的相关性均值）
- 新增 **partial-hit 错误分类**（`0.3 ≤ CP < 0.5 AND AR ≥ 0.7`）

**第三轮**：指标可信。

### 核心发现

**Hybrid（向量+BM25+RRF+Rerank）在 Markdown 表格密集题上 CP@3 反而退化 33%-67%。**

根因：3 篇 Markdown 文档高度共享关键词（"api-gateway" 出现在阈值表、聚合规则、故障复盘三处），BM25 无语义感知将关键词相关但语义无关的 chunk 推高排名，RRF 盲融合后污染 top-5 排名。

结论：**当前 KB 场景纯向量检索是最优策略**（CP@3=0.48, Faithfulness=0.97），推翻了"多路召回一定优于单路"的惯性假设。

### 最终评测结果（5 策略 × 15 题）

详见 `apps/backend/tests/data/eval_results/eval_latest.json`。

---

## 二、工具输出压缩

### 文件：`src/super_ai/chat/memory.py`、`src/super_ai/chat/streaming.py`

### 做了什么

1. **`maybe_compress_tool_output()`**：工具输出超过 2000 tokens 时自动调用 LLM 摘要压缩，压缩失败降级为截断

2. **`_wrap_tool_output_compression()`**：对所有异步 StructuredTool 透明包装压缩逻辑，Agent 无感知

### 设计要点

- 阈值：`TOOL_OUTPUT_COMPRESS_THRESHOLD_TOKENS = 2000`
- Token 估算：`len(text) // 4`（粗略近似）
- LLM 压缩失败 → 截断到 4000 字符 + 提示信息
- 同步工具（如 `get_current_time`）不包装——它们的输出总是很小

---

## 三、文档读取工具

### 文件：`src/super_ai/retrieval/read_document_tool.py`

### 做了什么

新增 `read_document` Agent 工具，允许 Agent 按文档 ID 读取知识库中的完整文档内容。

### 设计要点

- 遍历用户可访问的知识库，查找指定文档
- 读取 `document.metadata["indexableText"]`
- 超长文档截断到 `MAX_DOCUMENT_LENGTH_CHARS` 并添加省略提示
- 文档不存在时返回明确的 "Document not found" 消息
- 通过 `StructuredTool.from_function(coroutine=...)` 注册为异步 LangChain 工具

---

## 四、暗色模式与输入框改进

### 文件：前端 14 个文件

### 做了什么

1. **暗色模式**：
   - 新增 `stores/theme.ts`：Pinia 主题 store，支持 light/dark 切换 + localStorage 持久化
   - `styles.css` 新增 `[data-theme='dark']` 选择器，定义 ~38 个暗色 CSS 变量
   - `WorkspaceLayout.vue` 新增太阳/月亮切换按钮
   - `main.ts` 挂载前读取主题 store，消除加载闪烁
   - 批量替换 12 个组件的硬编码色值为 CSS 变量

2. **输入框自适应**：
   - `ChatComposer.vue`：textarea 高度随内容自动调整（最小 1 行，最大 6 行）

---

## 五、Task 2：LoopX Interaction Contract（诊断 Agent 决策升级）

### 改动文件：`src/super_ai/aiops/diagnostics.py`（~95 行）

### 问题

`_replanner()` 原先只有二元决策：

```python
continue_execution = plan_index < len(plan) and not execution_failed
decision = "continue" if continue_execution else "report"
```

遇到连续工具失败只会傻傻重试直到计划耗尽，没有自愈能力。

### 方案

引入 LoopX 的 4 种交互契约，让 Replanner 能根据执行状态做出差异化决策：

| 契约 | 触发条件 | Agent 行为 |
|------|---------|-----------|
| `bounded_delivery` | 计划未耗尽且上一步成功 | 正常执行下一步 |
| `autonomous_replan` | 连续 ≥2 步失败 | 放弃当前计划步骤，Executor 注入 KB 检索替代方案 |
| `outcome_floor_recovery` | 工具失败且零证据积累 | 降级为纯 KB 检索，至少收集文档排查路径 |
| `report` | 计划耗尽 | 进入报告生成 |

### 实现细节

1. **`AiopsDiagnosticState`** 新增 `consecutive_failures: int` 和 `contract: str`

2. **`_executor()`** 维护连续失败计数器（成功清零、失败 +1）。当 contract 为 `autonomous_replan` 或 `outcome_floor_recovery` 时，自动将当前步骤替换为 `knowledge_retrieval` 兜底查询

3. **`_replanner()`** 新增静态方法 `_determine_contract()`：

```python
@staticmethod
def _determine_contract(*, plan_index, plan_length, execution_failed,
                         consecutive_failures, has_evidence) -> str:
    plan_exhausted = plan_index >= plan_length
    if not plan_exhausted and consecutive_failures == 0:
        return "bounded_delivery"
    if consecutive_failures >= 2:
        return "autonomous_replan"
    if execution_failed and not has_evidence:
        return "outcome_floor_recovery"
    return "report"
```

4. 契约信息和连续失败计数写入 step payload 和 checkpoint，前端可通过 SSE `task.status` 事件获取 `contract` 字段区分 Agent 当前状态

5. `_route_after_replanner()` 无需改动——路由仍基于 `continue_execution` 标志（`report` 契约设 `continue_execution=False`，其余为 `True`）

---

## 六、Task 3：Bayesian SOP Evolution（SOP 闭环进化）

### 新增文件：`src/super_ai/aiops/sop_belief.py`（~260 行）
### 改动文件：`src/super_ai/aiops/diagnostics.py`（~30 行）

### 问题

SOP 当前是静态的——通过 seed 脚本写入数据库，检索排名只看向量相似度。每次诊断的验证结果没有反馈到 SOP 质量改进。反复导致失败的 SOP 无法自动识别和标记。

### 方案

引入 Bayesian-Agent 模式的 SOP 信念系统（参考 Wu et al., 2026, arXiv:2606.08348）。

#### sop_belief.py — 核心注册表

**`DiagnosticEvidence`**：诊断结果证据记录
- 字段：task_id, sop_id, context（场景标签如 "P0:api-gateway"）, outcome（success/failure）, failure_mode, total_tokens, turns, elapsed_seconds, metadata

**`SopBeliefState`**：每个 SOP 的 Beta-Bernoulli 后验信念
- alpha/beta 带 Laplace 平滑（alpha=1），防止小样本极端估计
- `success_probability` 属性：`alpha / (alpha + beta)`（后验成功率）
- 维护失败模式分布（`failure_modes`）、场景分布（`contexts`）、rolling mean 统计（token/turn/latency）
- `update(evidence)`：摄入新证据，自动更新所有统计量

**`SopBeliefRegistry`**：JSON 文件持久化注册表（`~/.oncall/sop_beliefs.json`）
- `record(evidence)`：摄入一条诊断证据 → 更新对应 SOP 的后验信念 → 持久化
- `top_sops(sop_ids, retrieval_scores)`：检索分 × 0.7 + 后验分 × 0.3 混合排序。观测 < 3 次的 SOP 仅信任检索分数（冷启动保护——样本不足时不使用信念）
- `get_rewrite_recommendations()`：为所有追踪 SOP 返回 RewritePolicy 决策
- `get_at_risk_sops(threshold)`：返回后验成功率低于阈值的 SOP 列表（供人工审核）

**RewritePolicy** — 5 种决策：

| 决策 | 触发条件 | 含义 |
|------|---------|------|
| `explore` | 观测数为 0 | 继续收集证据，不做修改 |
| `retire` | 失败 ≥4 且成功率 <45% | SOP 不可靠，标记废弃 |
| `patch` | 同一 failure_mode ≥2 次 | 生成针对性修复建议 |
| `split` | ≥3 个场景且 ≥4 次观测 | SOP 跨场景太广，需拆分 |
| `compress` | ≥3 次观测且成功率 ≥72% | SOP 稳定，可压缩上下文降 token |

关键设计：**一次失败只记录为审计证据，同一失败模式出现 ≥2 次才生成补丁**——防止对偶然噪声过拟合。

#### diagnostics.py — 两个集成点

**集成点 1：`_planner()` — 信念加权 SOP 排名**

在 SOP 检索后、生成诊断计划前，调用 `top_sops()` 混合排序。当信念系统调整了排名时，发出 SSE 状态事件告知前端。

```python
# 检索分 × 0.7 + 后验分 × 0.3，观测 < 3 次的 SOP 不启用信念（冷启动保护）
reranked_ids = self._sop_registry.top_sops(
    [payload["documentId"] for payload in sop_hits],
    retrieval_scores=retrieval_scores,
)
```

**集成点 2：`_report()` — 记录诊断证据**

诊断完成后（任务状态已确定为 succeeded/failed），为每个使用的 SOP 创建 `DiagnosticEvidence` 并记录到注册表。证据持久化异常不阻断诊断流程（`try/except` 包裹）。

---

## 验证方式

```bash
# 运行诊断相关测试（13 个）
cd apps/backend && uv run python -m pytest tests/ -v -k "diagnostic or aiops"

# 运行 sop_belief 核心逻辑验证
uv run python -c "
from super_ai.aiops.sop_belief import SopBeliefRegistry, DiagnosticEvidence, decide_rewrite
# ... 见源码注释中的 usage 示例
"

# 运行评测（生成最新报告）
cd apps/backend && uv run python tests/ragas_evaluation.py --limit 3

# 查看缓存的最新评测报告
cd apps/backend && uv run python tests/ragas_evaluation.py --report
```
