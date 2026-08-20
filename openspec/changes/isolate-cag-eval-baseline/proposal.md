## Why

`tests/cag_runner.py` 作为 CAG 研究基线直接手写 KV Cache、依赖 transformers 5.x 内部 API（DynamicLayer），却把 torch / transformers / bitsandbytes / accelerate 等重 ML 依赖放进运行时 dependencies，生产 `uv sync` 需拉取数 GB。

## What Changes

- `cag_runner.py` 标记为独立实验入口（docstring 注明安装方式）
- 重 ML 依赖移出运行时 dependencies，放入可选 `eval` dependency group
- 默认 `uv sync` 不再安装重 ML 依赖；仅评测 workflow 用 `uv sync --group eval`

## Capabilities

纯依赖与工程边界调整，不修改任何产品能力，`skip_specs: true`。

## Impact

- 后端 pyproject 依赖与锁文件
- CAG 实验脚本文档说明
- 评测 workflow 安装命令
- OpenSpec WIKI 与问题 11 记录
