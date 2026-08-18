# 问题 11：解决方案

## 计划

1. 新增 Alembic 表保存 SOP belief state 和 belief evidence。
2. 记录 owner_user_id、tenant_id、document_id、document_version、task_id。
3. 通过 Repository 读写，并纳入现有权限过滤和审计。
4. 迁移旧 JSON 时生成一次性导入记录，不直接把共享数据复制给所有用户。
5. 在迁移完成前禁止新旧存储双写产生不一致；完成后再删除文件依赖。

## 验收标准

- 不同用户、知识库和文档版本的 belief 相互隔离。
- 多进程更新具备事务和并发语义。
- belief evidence 可按诊断任务回溯。
