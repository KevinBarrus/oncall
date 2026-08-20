## Context

问题6 已建立 `.github/workflows/ci.yml` 与 `.github/workflows/evaluation.yml`。问题22 的诉求（自动门禁 + 评测不阻塞提交）主体已完成；剩余缺口是评测辅助函数测试只显式跑 `aiops_evaluation.py`，`rag_evaluation.py` 的辅助测试未进 CI。

## Goals / Non-Goals

**Goals:**

- 核对并确认 CI 门禁覆盖问题22 的全部诉求
- 将 RAG 评测辅助函数测试纳入 CI，防止评测逻辑回归

**Non-Goals:**

- 不新增重复的 CI job（复用问题6 的 ci.yml/evaluation.yml）
- 不把需要外部服务或 GPU 的评测并入主门禁

## Decisions

- ci.yml 的 "Evaluation helper tests" 步骤扩展为同时跑 `aiops_evaluation.py` 与 `rag_evaluation.py`
- 主门禁仍为 `uv sync`（不装 eval group），评测辅助测试不依赖 ML 库
- 评测 workflow（RAG/AIOps）保持手动与定时触发

## Risks / Trade-offs

- [评测辅助测试增加 CI 时长] → 两文件合计约数十秒，可接受

## Migration Plan

无变更。仅 CI 配置步骤调整与记录。
