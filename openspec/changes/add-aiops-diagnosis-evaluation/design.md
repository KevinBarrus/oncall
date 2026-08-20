## Context

现有测试只验证诊断管线的 plumbing（工具调用、证据持久化、失败路径），RAG 评测也只覆盖检索+生成。AIOps 诊断的差异化能力（Plan-Execute-Replan、SOP 信念）缺少端到端量化指标。

## Goals / Non-Goals

**Goals:**

- 用固定已标注故障案例量化诊断质量：根因命中、证据覆盖、修复建议可执行、无答案拒答、延迟
- 离线验证 SOP 信念加权会改变检索排序（机制验证）
- 辅助函数测试进 CI，端到端评测进手动/定时 workflow

**Non-Goals:**

- 不用信念后验分数作为诊断效果提升的证明；排序对比仅为机制验证
- 不把端到端评测纳入普通提交门禁（依赖真实后端、Milvus、LLM 与 CLS MCP）

## Decisions

- 数据源复用 `JAVA_ECOMMERCE_INCIDENTS`（10 套含真实根因与恢复步骤的标注案例），不新增平行案例集
- 指标判定用 jieba token 召回阈值与确定性标记，不引入 LLM-as-judge
- 端到端评测通过 HTTP API 创建诊断任务并读取证据链，指标函数离线可单测
- SOP 排序对比用纯函数模拟 `top_sops` 加权，验证信念可改变排名

## Risks / Trade-offs

- [根因/恢复命中依赖报告措辞] → 用 token 召回而非精确匹配，阈值可调；误判为安全（指标偏低而非错误结论）
- [端到端评测需要外部服务] → 定位为手动/定时 job，不阻塞普通提交

## Migration Plan

无 schema 变更。新增评测脚本与 workflow 即可，回滚即删除。
