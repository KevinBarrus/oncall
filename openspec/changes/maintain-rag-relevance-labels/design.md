## Context

`_manual_relevance_labels` 用 `_normalise_evidence(fact) in _normalise_evidence(chunk.content)` 精确子串判定 2 分；`_atomic_fact_recall_at_k` 同样依赖精确子串。55 条事实实测只有 49% 能精确命中源文档，其余因"超过/高于"、"800ms/800 毫秒"等措辞与符号差异漏判。

## Goals / Non-Goals

**Goals:**

- 相关性判定容忍改写，同时避免短事实被功能词稀释而误判
- 修正标注数据，使每个 atomic_fact 都能在源文档中定位（可审计）
- 扩充改写、跨文档推理案例，保持无答案拒答覆盖

**Non-Goals:**

- 不改变评测策略与指标定义
- 不引入 LLM-as-judge 做相关性标注

## Decisions

- 新增 `_fact_matches_chunk`：取事实的"内容 token"（过滤单字符、纯符号与功能词集合），按 token 召回率 ≥0.4 判定匹配
- 新增 `_FACT_STOP_TOKENS` 功能词集合与 `_is_pure_symbol` 过滤，解决"阈值/超过/为"等通用 token 造成的短事实误判
- 数据修正：移除 QA[7] 推理事实"底层问题传导到用户体验"，QA[17] "减少通知噪音"改为文档字面"抑制同因告警"
- 数据扩充：新增 3 条 QA（改写×2 + 跨文档×1），全部事实经 token 召回验证可定位

## Risks / Trade-offs

- [功能词集合需随数据演进维护] → 集合覆盖常见中文功能词，新增数据时按匹配率回归校验
- [token 召回可能误报相关] → 阈值 0.4 + 内容 token 过滤，实测数据集匹配率 100% 且无关 chunk 拒绝测试通过

## Migration Plan

无 schema 变更。改动评测脚本与数据文件，`uv run pytest tests/rag_evaluation.py` 验证辅助函数测试。
