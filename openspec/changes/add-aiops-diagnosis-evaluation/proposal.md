## Why

RAG 问答已有量化评测，但 AIOps Plan-Execute-Replan 诊断质量没有任何端到端量化指标，无法回答"诊断对了几次、根因命中率多少"；SOP 贝叶斯信念更新是否改变检索排序也从未被独立验证。

## What Changes

- 新增 AIOps 诊断质量评测脚本，复用 Java 电商 10 套已标注故障案例作为 golden 数据
- 采集诊断报告与证据链，计算根因命中率、证据覆盖率、修复建议可执行率、无答案拒答率和端到端延迟
- 离线对比 SOP 检索排序在信念加权前后的排名变化（机制验证，不作效果证明）
- 评测辅助函数测试纳入 CI 门禁，端到端评测作为手动/定时 workflow

## Capabilities

### New Capabilities

- `aiops-diagnosis-evaluation`: AIOps 诊断链路的量化质量评测

### Modified Capabilities

- `aiops-diagnosis-tasks`: 提供评测可复用的已标注故障案例与报告/证据链读取

## Impact

- 新增 tests/aiops_evaluation.py 评测脚本
- CI 与评测 workflow 更新
- OpenSpec WIKI 与问题 7 记录
