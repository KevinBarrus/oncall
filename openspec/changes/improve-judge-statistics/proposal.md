## Why

LLM-as-judge 用 DeepSeek 评 Qwen 生成内容（跨模型裁判），`_parse_score` 只接受纯数字、带解释即判无效，抬高 judge failure rate；单次打分无置信区间，报告未标注 Judge 局限。

## What Changes

- judge prompt 改为 JSON 评分格式（score + explanation），`_parse_score` 优先解析 JSON、回退纯数字
- 每次 judge 打分默认重复采样 3 次，记录均值、标准差、有效样本数与失败次数
- `judge_failure_rate` 改为按 judge 调用次数统计，报告有效样本数
- 报告标注 Judge 模型、地址与跨模型裁判局限，输出 LLM 指标均值±std

## Capabilities

纯评测工具链改进，不修改任何产品能力，`skip_specs: true`。

## Impact

- 评测脚本 Judge 打分、聚合与报告
- 评测辅助函数测试
- OpenSpec WIKI 与问题 10 记录
