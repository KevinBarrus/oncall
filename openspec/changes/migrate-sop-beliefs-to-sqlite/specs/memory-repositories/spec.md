## ADDED Requirements

### Requirement: SOP 信念使用受作用域约束的 Repository

系统 SHALL 通过既有 Repository 层读写 SOP 信念状态和证据，领域服务不得直接依赖 JSON 文件或 ORM 会话。Repository 的查询和更新接口必须显式接收当前用户与租户作用域。

#### Scenario: Repository 只返回当前作用域的 SOP 记录

- **WHEN** 领域服务按当前用户和租户查询 SOP 信念
- **THEN** Repository 只返回匹配该作用域的状态和证据
- **AND** 调用方无需了解底层 SQLite 表结构

#### Scenario: 数据库迁移创建 SOP 信念存储

- **WHEN** 在新数据库执行全部 Alembic 迁移
- **THEN** 数据库包含 SOP 信念状态和证据所需的表及作用域查询索引
