## Context

问题8（RAGAS 名不副实）已移除 `ragas` 运行时依赖；问题11（隔离 CAG 研究基线）已将 torch/transformers/bitsandbytes/accelerate 移入可选 `eval` dependency group。问题21 剩余的诉求是核对依赖分层并确认无评测专属重依赖残留。

## Goals / Non-Goals

**Goals:**

- 确认运行时 dependencies 不再包含重 ML 评测依赖
- 确认 CI 分层：主门禁不安装 eval group，评测 job 显式安装

**Non-Goals:**

- 不把轻量评测依赖（jieba）移出运行时——其体积小且 CI 评测辅助测试需要
- 不改变已完成的依赖隔离实现（问题8、问题11）

## Decisions

- 运行时依赖逐项核对：`rank-bm25` 由 `src` 检索管线使用保留；`jieba` 仅评测用但为轻量纯 Python 库且 CI 需要，保留
- CI 主门禁 `uv sync`、RAG 评测 job `uv sync --group eval`、AIOps 评测 job `uv sync`
- 本项仅做核对与记录，不重复改动依赖

## Risks / Trade-offs

- [jieba 留在运行时仍属评测依赖] → 体积小、CI 辅助测试需要，留在运行时收益大于隔离成本

## Migration Plan

无变更。依赖分层已在问题8/11 落地，本项仅记录完成状态。
