## 1. 依赖提取

- [x] 1.1 新建 api/dependencies.py 共享依赖提供者

## 2. 路由迁移

- [x] 2.1 新建 api/routers/auth.py 并迁移 /auth/* 路由
- [x] 2.2 app.py include_router 挂载并删除 auth 路由与冗余辅助函数

## 3. 验证与记录

- [x] 3.1 认证 API 测试与全量回归通过
- [x] 3.2 更新问题 20 方案与 WIKI
