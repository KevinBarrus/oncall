## 1. 评分解析

- [x] 1.1 `_parse_score` 支持 JSON 评分格式并回退纯数字
- [x] 1.2 judge prompt 改为 JSON 输出（score + explanation）

## 2. 统计可信度

- [x] 2.1 `_llm_score` 重复采样，记录均值、标准差、有效样本与失败数
- [x] 2.2 `judge_failure_rate` 按调用次数统计并报告有效样本数

## 3. 报告与验证

- [x] 3.1 报告标注 Judge 模型、地址与跨模型裁判局限，输出 LLM 指标均值±std
- [x] 3.2 补充 JSON 解析、重复采样与部分失败测试，更新问题 10 方案与 WIKI
