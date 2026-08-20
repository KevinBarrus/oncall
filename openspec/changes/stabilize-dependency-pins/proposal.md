## Why

`langchain>=1.3.12` 无上限，`create_agent` API 在 LangChain 1.x 不稳定；CAG 实验依赖 `transformers>=5.14.1`、`torch>=2.13.0` 是未稳定新大版本，`cag_runner.py` 依赖 transformers 5.x 内部 API（DynamicLayer），`uv sync` 存在解析漂移风险。

## What Changes

- 确认 `uv.lock` 已提交并被 CI 使用，开发/CI/部署使用同一解析结果
- `langchain` 设上限 `<2.0`，限制在已验证的 1.x 范围
- eval group 的 torch/transformers/accelerate/bitsandbytes 固定版本，避免内部 API 漂移

## Capabilities

纯依赖约束调整，不修改任何产品能力，`skip_specs: true`。

## Impact

- 后端 pyproject 依赖约束与锁文件
- OpenSpec WIKI 与问题 28 记录
