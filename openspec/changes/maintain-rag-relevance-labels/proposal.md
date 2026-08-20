## Why

RAG 评测的 chunk 相关性标注依赖"去空白后的精确子串匹配"，改写（paraphrase）后的事实匹配不上会被判 0 分；实测 55 条 atomic_facts 精确匹配率仅 49%，评测的 MRR/NDCG/Recall 指标被措辞差异系统性低估。gold source 只有 3 篇文档、24 条查询，规模为 demo 级。

## What Changes

- 将 chunk 相关性判定从精确子串匹配改为内容 token 召回（jieba），过滤单字符、符号与功能词，容忍改写措辞
- 修正无法在文档定位的推理事实，保证人工标注可审计
- 扩充 QA 数据集，纳入改写（paraphrase）与跨文档推理案例，保留无答案案例

## Capabilities

纯评测工具链改进，不修改任何产品能力，`skip_specs: true`。

## Impact

- 评测脚本相关性标注函数与数据文件
- 评测辅助函数测试
- OpenSpec WIKI 与问题 9 记录
