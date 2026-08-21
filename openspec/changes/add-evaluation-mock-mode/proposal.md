## Why

端到端评测（AIOps/RAG）依赖真实后端、Milvus、LLM 与 CLS MCP，本地未起服务时无法离线验证评测管线，指标计算回归只能等定时任务。

## What Changes

- `tests/aiops_evaluation.py` 新增 `--mock`：确定性 mock 报告走同一套指标与汇总管线
- `tests/rag_evaluation.py` 新增 `--mock`：跳过外部依赖，用 fixture chunks + 确定性 answer/judge
- mock 管线测试加入 pytest（CI 自动运行）

## Capabilities

纯评测工具链改进，不修改任何产品行为，`skip_specs: true`。

## Impact

- 两个评测脚本的 mock 模式与测试
- .gitignore 补充 aiops 评测结果目录
