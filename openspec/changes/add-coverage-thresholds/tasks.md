## 1. 覆盖率配置

- [x] 1.1 pytest-cov 依赖 + [tool.coverage] 配置（source/fail_under=80）
- [x] 1.2 scripts/check_coverage.py 域阈值检查

## 2. CI 接入

- [x] 2.1 CI Coverage 步骤（--cov-fail-under=80 + 域检查）

## 3. 验证与记录

- [x] 3.1 本地验证：全局 86.6%、auth 94%、chat 81%、aiops 83% 全部通过
- [x] 3.2 更新问题 28 记录与 WIKI
