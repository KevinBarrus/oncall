## Why

评测脚本 `ragas_evaluation.py` 手写全部指标（直接 prompt LLM），从不 import `ragas`，但 `pyproject.toml` 把 `ragas>=0.4.3` 列为运行时依赖；名字、依赖、实现三者不一致，且 ragas 及其重依赖（pillow、pyarrow、scipy 等）拖累安装体积。

## What Changes

- 保留自定义 Judge 指标实现，将 `tests/ragas_evaluation.py` 改名为 `tests/rag_evaluation.py`
- 配套 `setup_ragas_kb.py`、`rag_test_qa.json` 数据文件同步改名，类名改为 `TestRagEvaluation`
- 移除 `ragas>=0.4.3` 运行时依赖并更新 uv.lock
- 评测账号与环境变量统一改为 `rag-eval` / `RAG_API_BASE_URL`，更新 workflow 与 ruff/pyright exclude 引用

## Capabilities

纯评测工具链重构，不修改任何产品能力，`skip_specs: true`。

## Impact

- 评测脚本与配套数据文件改名
- 后端 pyproject 依赖与锁文件
- 评测 workflow 与 ruff/pyright exclude 引用
- OpenSpec WIKI 与问题 8 记录
