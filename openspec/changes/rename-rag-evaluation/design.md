## Context

RAG 评测使用自定义 Judge 指标（DeepSeek prompt 打分）与确定性指标（MRR/NDCG/Recall），从未调用 ragas 库。`ragas>=0.4.3` 是死依赖，且作为运行时依赖引入 pillow、pyarrow、scipy、scikit-network 等重依赖。

## Goals / Non-Goals

**Goals:**

- 消除"RAGAS"名称与实现的误导，统一为项目自己的 RAG 评测
- 移除未使用的 ragas 运行时依赖及其传递依赖
- 更新所有代码、配置、workflow 引用，保持可运行

**Non-Goals:**

- 不切换到真实 RAGAS 库（自定义指标已投入且无需迁移）
- 不改动评测指标逻辑与策略实现

## Decisions

- 文件改名：`ragas_evaluation.py` → `rag_evaluation.py`、`setup_ragas_kb.py` → `setup_rag_kb.py`、`ragas_test_qa.json` → `rag_test_qa.json`
- 保留 `git mv` 历史，用 sed 同步替换文档字符串、数据文件引用、评测账号（`rag-eval@agent-py.local` / `rag-test-123456`）与环境变量（`RAG_API_BASE_URL`）
- ruff/pyright exclude 与评测 workflow 同步更新为新文件名
- 用 `uv lock` 重新解析依赖，移除 ragas 及其传递依赖

## Risks / Trade-offs

- [历史文档仍引用旧文件名] → problem-tracker、CAG_HANDOFF、WORK_DONE 为历史记录，保留原样；现状由 solution2 问题8 记录
- [评测账号变更] → 评测账号是脚本自动注册/登录的测试账号，改名无迁移成本

## Migration Plan

无 schema 变更。改名后 `uv sync` 重新解析依赖；旧命令 `ragas_evaluation.py` 不再可用，需使用 `rag_evaluation.py`。
