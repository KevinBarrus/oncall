## Context

现有验证命令（ruff、pyright、pytest、前端 typecheck/test/build、契约检查）都能本地运行，但没有 CI 强制执行；评测脚本 ragas_evaluation.py 需要 SILICONFLOW_API_KEY、DEEPSEEK_API_KEY 与运行中的 Milvus，无法作为普通提交门禁。

## Goals / Non-Goals

**Goals:**

- 用 GitHub Actions 强制执行无需外部依赖的检查，作为每次 push/PR 的门禁
- 端到端评测作为手动或定时 job，需要密钥时从 secrets 注入
- 让离线回归集在干净 checkout 环境可运行

**Non-Goals:**

- 不在 CI 里修复仓库卫生问题（如模板文件未提交、.gitignore 精确策略）；本地配置测试仅标记隔离
- 不接入 LLM-as-judge 到 CI，也不把评测脚本并入主门禁

## Decisions

- 后端 job 用 `pytest -m "not local_config"` 排除依赖本地 config/project.json 的测试；ruff/pyright 排除评测与实验脚本（ragas_evaluation.py、cag_runner.py、setup_ragas_kb.py）与历史迁移目录
- 前端与契约 job 复用根 package.json 的 workspace 脚本，Node 版本固定 22
- 评测 workflow 用 `workflow_dispatch` + 每周定时，Milvus 由 compose 起并通过 `--wait` 等待健康

## Risks / Trade-offs

- [CI 首次运行可能暴露新环境差异] → 以本地验证命令为准，CI 失败按日志单独修复
- [评测 job 需要仓库 secrets] → 未配置密钥时手动触发会失败，属预期；不影响主门禁

## Migration Plan

无 schema 变更。新增 workflow 文件与配置即可，回滚即删除 workflow。
