## Context

`_parse_score` 用 `re.fullmatch` 只接受纯数字（0.0-1.0），judge 输出带解释即返回 invalid_score；`_llm_score` 单次打分，无方差；报告只显示 Judge 模型名，未标注跨模型偏差。

## Goals / Non-Goals

**Goals:**

- 降低 judge 解析失败率：带解释的 JSON 输出也能解析
- 通过重复采样给出均值与标准差（方差），报告有效样本数与失败率
- 在报告中显式标注 Judge 模型与跨模型裁判局限

**Non-Goals:**

- 不更换 Judge 模型（保留 DeepSeek 跨模型裁判，仅标注局限）
- 不改变评测策略与确定性指标

## Decisions

- `_parse_score` 优先从 judge 输出提取 JSON 的 `score` 字段（0.0-1.0），失败时回退纯数字 fullmatch；新增 `_score_from_json` 与 `_bounded_score`
- `_llm_score(judge_model, prompt, samples=3)` 重复采样，`JudgeScore` 增加 `samples`、`failures`、`std` 字段；全失败时保留异常类名
- 每个 judge prompt 要求输出 `{"score": 0-1 数字, "explanation": "简短理由"}`，带解释输出不再判无效
- `judge_failure_rate` 按总失败调用 / 总调用统计（从 perItem 的 `judgeStats` 聚合），替代按 item 计数
- 报告新增 Judge 说明（模型、地址、跨模型局限）与每个策略 LLM 指标均值±std

## Risks / Trade-offs

- [重复采样增加 judge 调用成本] → 默认 3 次可调，DeepSeek 成本可控
- [JSON 解析可能被恶意/异常输出绕过] → score 必须 0.0-1.0 且优先 JSON 的 score 字段，越界判无效

## Migration Plan

无 schema 变更。改动评测脚本与测试，`uv run pytest tests/rag_evaluation.py` 验证辅助函数测试。
