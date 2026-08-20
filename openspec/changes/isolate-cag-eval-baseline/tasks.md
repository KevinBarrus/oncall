## 1. 依赖隔离

- [x] 1.1 重 ML 依赖移出运行时 dependencies，放入可选 `eval` group
- [x] 1.2 更新 uv.lock，默认 `uv sync` 不再安装 torch 等

## 2. 实验入口

- [x] 2.1 `cag_runner.py` docstring 标记独立实验入口与安装方式

## 3. 验证与记录

- [x] 3.1 评测 workflow 改用 `uv sync --group eval`，CI 主门禁保持默认
- [x] 3.2 更新问题 11 方案与 WIKI
