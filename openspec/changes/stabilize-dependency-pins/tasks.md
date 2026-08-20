## 1. 依赖约束

- [x] 1.1 `langchain` 设上限 `<2.0`
- [x] 1.2 eval group 固定 torch/transformers/accelerate/bitsandbytes 版本

## 2. 验证

- [x] 2.1 `uv lock` 无冲突，默认环境不安装重 ML 依赖
- [x] 2.2 回归测试与 lint 通过

## 3. 记录

- [x] 3.1 更新问题 28 方案与 WIKI
