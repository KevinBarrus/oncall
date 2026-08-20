## Context

app.py 内部定义所有路由（`@app.*` 装饰器）与模块级辅助函数。迁移 auth 域需要解决跨路由共享依赖的复用问题，否则 router 模块会与 app.py 产生循环依赖。

## Goals / Non-Goals

**Goals:**

- 建立可复用的路由拆分模式（dependencies + domain routers）
- 迁移 auth 域作为示范，验证行为与契约不变
- 为后续 chat/knowledge/aiops/mcp 渐进迁移提供模式

**Non-Goals:**

- 不一次性拆分全部路由（方案明确渐进）
- 不改变任何路由路径、请求/响应结构、错误码

## Decisions

- 新建 `api/dependencies.py`：承载 `bearer_scheme`、`BearerCredentials`、`current_user`、`auth_service`、`memory_repositories`、`bearer_token`、`api_error` 等跨路由共享依赖，公开命名避免 pyright reportPrivateUsage
- 新建 `api/routers/auth.py`：`/auth/*` 4 个路由 + RegisterRequest/LoginRequest 模型 + payload 序列化函数
- app.py 从 dependencies import 共享依赖（`current_user`、`memory_repositories`），`include_router(auth_router.router)` 挂载，删除 auth 路由与冗余辅助函数
- `/me` 路由 handler 命名为 `me`，避免与依赖函数 `current_user` 冲突

## Risks / Trade-offs

- [依赖提取涉及 app.py 大量引用] → 用公开命名 + sed 机械替换，靠 test_auth_api 与全量回归验证
- [剩余路由仍集中在 app.py] → 符合渐进原则，后续路由修改时迁移

## Migration Plan

无 schema 变更。auth 路由路径与契约不变，存量测试即可验证。
