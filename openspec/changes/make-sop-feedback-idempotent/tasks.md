## 1. 幂等持久化

- [x] 1.1 新增 SOP 反馈 submission 模型、Repository 数据记录和 Alembic migration，并建立 owner/tenant/task/rating 唯一约束
- [x] 1.2 扩展 Repository 契约并实现单事务的 SQLite `record_feedback_once`，使 claim、manual evidence 与 posterior 更新原子完成

## 2. 诊断反馈接入

- [ ] 2.1 改造 SOP belief service 与诊断反馈路由：重放仅返回状态，不再重复更新后验

## 3. 验证与追踪

- [ ] 3.1 添加同评分重放、不同评分、并发提交和跨 owner 隔离测试
- [ ] 3.2 运行目标 pytest、Ruff、Pyright、Alembic upgrade 和 OpenSpec 校验，并同步 problem tracker
