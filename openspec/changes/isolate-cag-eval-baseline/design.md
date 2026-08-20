## Context

`rag_evaluation.py` 的 `cag-kvcache` 策略在运行时惰性 import `cag_runner`，只有该策略需要 torch/transformers；`apps/backend/src` 对这四个 ML 包零 import。生产服务安装却要下载 torch 生态。

## Goals / Non-Goals

**Goals:**

- 默认 `uv sync` 不安装重 ML 依赖，生产与 CI 主门禁不再拉取 torch
- CAG 实验仍可通过显式 group 安装运行
- 明确 `cag_runner.py` 的独立实验入口定位

**Non-Goals:**

- 不修改 `cag_runner.py` 的模型加载与 KV Cache 实现
- 不为 CAG 固化容器镜像（当前以 dependency group 隔离，容器固化留待实验定型后）

## Decisions

- 运行时 `dependencies` 移除 accelerate / bitsandbytes / torch / transformers
- 新增 `[dependency-groups] eval` 存放这四个依赖；`uv sync --group eval` 安装
- `cag_runner.py` docstring 声明为独立研究基线并注明安装命令
- 评测 workflow 的 RAG job 改用 `uv sync --group eval`；CI 主门禁保持默认 `uv sync`
- `uv.lock` 重新解析，torch 等保留在 eval group 的解析记录中，默认组不安装

## Risks / Trade-offs

- [本地跑 CAG 评测前需手动 `uv sync --group eval`] → docstring 与 workflow 均已注明
- [transformers 5.x 内部 API 不稳定] → 依赖固定在 lock 文件；实验定型后再固化容器

## Migration Plan

无 schema 变更。改动依赖配置与 workflow，`uv sync` 后默认环境不再包含重 ML 依赖。
