## Why

问题22 要求建立最小 CI 门禁（后端 Ruff/Pyright/pytest + 前端与契约检查），外部评测用手动/定时 workflow。CI 主体已由问题6 建立，本次核对覆盖范围并把评测辅助函数测试完整纳入门禁。

## What Changes

- 核对 CI 门禁覆盖：后端 ruff/pyright/离线 pytest、前端 typecheck/test/build、契约 typecheck/test
- 评测 workflow（RAG 与 AIOps）作为手动/定时入口，不阻塞普通提交
- 评测辅助函数测试补充纳入 CI（`aiops_evaluation.py` + `rag_evaluation.py`）

## Capabilities

纯 CI 配置维护，不修改任何产品能力，`skip_specs: true`。

## Impact

- CI workflow 配置
- OpenSpec WIKI 与问题 22 记录
