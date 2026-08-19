## 1. 归因存储

- [x] 1.1 新增 SOP 候选曝光表、记录类型、Repository 接口和 SQLite 实现，并增加 Alembic migration。
- [x] 1.2 为可更新的 SOP evidence 增加归因阶段与证据强度字段，保持旧记录可读取。

## 2. 诊断归因链路

- [x] 2.1 扩展 Planner 输出和验证器，接收并校验 `sopDocumentIds`。
- [x] 2.2 持久化所有候选 SOP 的曝光记录，但不更新后验状态。
- [x] 2.3 仅依据已验证的计划 SOP 引用写入结果 evidence，并将归因元数据传给 belief service。

## 3. 验证与追踪

- [x] 3.1 添加测试，覆盖候选不更新后验、计划引用更新、曝光和结果归因字段、owner 隔离。
- [ ] 3.2 运行目标 pytest、Ruff、Pyright、Alembic upgrade 和 OpenSpec 校验，并同步 problem tracker。
