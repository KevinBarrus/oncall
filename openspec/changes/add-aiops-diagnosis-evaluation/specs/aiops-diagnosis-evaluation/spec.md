## ADDED Requirements

### Requirement: AIOps diagnosis quality evaluation
后端 SHALL 提供基于已标注故障案例的 AIOps 诊断质量评测，采集诊断报告与证据链并计算根因命中率、证据覆盖率、修复建议可执行率、无答案拒答率和端到端延迟，指标函数 MUST 可离线单测。

#### Scenario: Evaluation helper tests run in CI
- **WHEN** 评测辅助函数测试被显式执行
- **THEN** 指标判定、案例数据加载与 SOP 排序对比 MUST 在无外部服务环境下通过

### Requirement: SOP belief ranking mechanism verification
评测 SHALL 提供 SOP 检索排序在信念加权前后的排名对比，用于机制验证，MUST NOT 以后验分数作为诊断效果提升的证明。

#### Scenario: Belief promotes the correct SOP
- **WHEN** 正确 SOP 检索分靠后但信念分高
- **THEN** 加权排序 MUST 将正确 SOP 排名提前，评测输出两种排序下的排名
