## ADDED Requirements

### Requirement: Automated regression gates
仓库 SHALL 使用 GitHub Actions 在每次 push 与 pull request 上强制执行无需外部依赖的检查，包括后端 ruff、pyright 与离线 pytest，以及前端与共享契约的 typecheck、test 和 build。

#### Scenario: Offline checks run on every change
- **WHEN** 开发者向 main 推送或提交 pull request
- **THEN** CI MUST 运行后端 lint、类型检查和离线回归测试，以及前端与契约检查

### Requirement: Layered evaluation entry
需要外部服务与密钥的多策略 RAG 评测 SHALL 通过手动或定时 workflow 运行，MUST NOT 阻塞普通提交。

#### Scenario: Evaluation runs on demand or schedule
- **WHEN** 维护者手动触发或到达定时计划
- **THEN** 后端 MUST 启动 Milvus 并从 secrets 注入评测密钥后运行评测脚本
