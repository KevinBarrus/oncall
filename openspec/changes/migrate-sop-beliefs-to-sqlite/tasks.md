## 1. SQLite 存储边界

- [x] 1.1 新增 SOP belief state/evidence ORM models、作用域索引和 Alembic revision。
- [x] 1.2 在 Repository contracts、records 与 SQLite repository bundle 中提供受 owner/tenant 约束的 SOP belief 查询和原子记录接口。

## 2. AIOps 调用链迁移

- [x] 2.1 将 `sop_belief.py` 改为无 JSON 依赖的领域对象与异步 SOP belief service。
- [x] 2.2 将诊断重排和诊断完成后的证据记录改为使用异步 service，并从知识文档解析 content-hash 版本。
- [x] 2.3 将诊断反馈路由与应用依赖装配改为使用 SQLite service，移除 JSON registry 和 `~/.oncall` 读写。

## 3. 验证与文档

- [x] 3.1 添加 Repository 测试，覆盖证据与后验原子更新、owner/tenant 隔离和文档版本隔离。
- [x] 3.2 添加诊断/反馈回归测试，确认重排与人工反馈仍返回既有 API 语义。
- [ ] 3.3 运行目标 pytest、Ruff、Pyright、Alembic upgrade 与 OpenSpec 校验，并将问题 11 状态同步到 problem tracker。
