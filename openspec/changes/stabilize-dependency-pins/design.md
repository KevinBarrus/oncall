## Context

`uv.lock` 已提交，`uv sync` 在开发与 CI 均以 lock 解析，解析漂移风险已基本受控；剩余缺口是 pyproject 的约束范围仍松（langchain 无上限、CAG 依赖无上限）。

## Goals / Non-Goals

**Goals:**

- 核心运行时依赖（langchain）设经验证兼容范围
- CAG 实验依赖固定版本，避免 transformers 5.x 内部 API 漂移，且不影响服务升级节奏

**Non-Goals:**

- 不逐包固定全部运行时依赖（lock 已提供确定性解析）
- 不升级或降级任何依赖版本

## Decisions

- `langchain>=1.3.12,<2.0`：`create_agent` API 在 1.x 验证过，禁止跨大版本漂移
- eval group 固定：`accelerate==1.14.0`、`bitsandbytes==0.50.0`、`torch==2.13.0`、`transformers==5.14.1`
- eval group 独立于运行时依赖，固定版本不影响运行时升级节奏

## Risks / Trade-offs

- [langchain <2.0 限制未来升级] → 有意为之：跨大版本需先验证 `create_agent` 兼容性再放开

## Migration Plan

无 schema 变更。改约束后 `uv lock` 重新解析（与已锁版本一致，无冲突），`uv sync` 验证。
