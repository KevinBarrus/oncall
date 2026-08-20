## Why

仓库没有任何 `.github/workflows`，lint、类型检查和测试全靠手工命令；唯一"评测"（ragas_evaluation.py）需要外部 API key、运行中的 Milvus 和后端，从未进入任何自动化门禁。

## What Changes

- 新增 CI 门禁，强制后端 ruff/pyright/离线 pytest 以及前端和契约的 typecheck/test/build
- 将需要外部服务的多策略 RAG 评测隔离为手动或定时 workflow，不阻塞普通提交
- 标记依赖本地配置文件的测试，使离线回归集可在干净环境运行

## Capabilities

### New Capabilities

- `ci-regression-gates`: GitHub Actions 自动门禁与分层评测入口

### Modified Capabilities

- `repo-hygiene`: 排除评测/实验脚本与历史迁移的 lint，注册本地配置测试标记

## Impact

- `.github/workflows` 新增 CI 与评测 workflow
- 后端 pyproject 的 ruff/pyright/pytest 配置
- 少量离线测试与前端测试漂移修复、OpenSpec WIKI 与问题 6 记录
