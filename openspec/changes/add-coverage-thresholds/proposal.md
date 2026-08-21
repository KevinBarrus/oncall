## Why

测试套件无覆盖率报告与阈值，无法得知关键模块覆盖情况，新增代码可能无测试但 CI 不告警。

## What Changes

- dev 组新增 pytest-cov
- `[tool.coverage]` 配置：source=super_ai、全局 fail_under=80
- `scripts/check_coverage.py`：auth/chat/aiops 三大关键域按目录聚合阈值（80/75/75%）
- CI 增加 Coverage 步骤（全局 fail-under + 域检查）

## Capabilities

纯 CI/工程门禁，不修改任何运行时行为，`skip_specs: true`。

## Impact

- pyproject.toml（依赖 + coverage 配置）、uv.lock
- scripts/check_coverage.py
- ci.yml Coverage 步骤
