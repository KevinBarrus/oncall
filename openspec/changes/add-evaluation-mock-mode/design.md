## Context

solution3.md 问题9：评测依赖外部 API 无离线回退。方案：mock fixture（3-5 案例）+ `--mock` 参数 + CI 跑 mock 评测。

## Goals / Non-Goals

**Goals:**

- 无外部依赖可离线跑通评测管线（指标计算、汇总、报告）
- mock 评测纳入 CI（pytest 辅助测试）

**Non-Goals:**

- 不 mock LLM judge 的解析逻辑（`_llm_score`/`_score_from_json` 已有单元测试覆盖）
- 不 mock 端到端 HTTP/SSE 路径（保留 evaluation.yml 手动/定时）

## Decisions

- **AIOps mock**：`_mock_evaluate_one_incident` 用 incident 数据构造确定性报告/证据/工具调用，走 `root_cause_hit` 等真实指标函数
- **RAG mock**：`_mock_retrieve` 从 ground_truth 切句构造 chunk（source 取标注引用，保证相关性标签非零）；`_mock_judge` 用 token 重叠出确定性分数；answer 取 ground_truth；跳过 baselines（gold/answer-injection 无 mock 意义）
- 两个脚本 `run_evaluation(mock=True)` 均可被 pytest 直接调用（新增管线测试，CI 自动运行）

## Risks / Trade-offs

- [mock 分数非真实 LLM 判断] → 目的仅为验证管线与指标计算，不替代真实评测
- [RAG baselines 跳过] → mock 下 payload 中 baseline 为空 dict，测试断言该结构

## Migration Plan

无 schema 变更。
