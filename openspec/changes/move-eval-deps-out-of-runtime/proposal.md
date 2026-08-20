## Why

运行时 dependencies 曾包含 torch、transformers、bitsandbytes、accelerate、ragas 等评测专属依赖，而 `apps/backend/src` 零 import，生产 `uv sync` 需拉取数 GB 的 torch 生态。

## What Changes

- 确认重 ML 依赖已全部移出运行时 dependencies：`ragas` 在问题8 移除，torch/transformers/bitsandbytes/accelerate 在问题11 移入可选 `eval` group
- CI 主门禁保持默认 `uv sync`，评测 workflow 的 RAG job 使用 `uv sync --group eval`
- 核对剩余运行时依赖均由 `src` 使用或属轻量评测依赖（jieba 保留）

## Capabilities

纯依赖与工程边界确认，不修改任何产品能力，`skip_specs: true`。

## Impact

- 依赖分层状态记录
- OpenSpec WIKI 与问题 21 记录
