# 问题 10：解决方案

## 计划

1. 将现有实验改名为 `answer_injection_sanity_check`。
2. 新增基于原始 gold 文档全文或人工选定证据的 generation baseline。
3. 明确两者分别回答“模型能否利用标准答案”和“模型能否利用真实文档”。
4. 报告中不再把 answer injection 直接称为检索系统理论上界。

## 验收标准

- 两类 baseline 分列展示。
- 指标说明清楚上下文来源。
- 结论不把答案注入结果解释为真实 RAG 上界。
