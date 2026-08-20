## Why

`api/app.py` 是 2887 行的"上帝文件"：约 57 个路由、所有依赖提供者与 payload 序列化堆在一起，违反"职责单一"原则。一次性重写风险高，需按方案渐进拆分。

## What Changes

- 建立 `api/dependencies.py` 共享依赖提供者（认证、存储仓库等跨路由依赖）
- 建立 `api/routers/` 包，将 auth 域 4 个路由迁移到 `routers/auth.py`
- app.py 以 `include_router` 挂载 auth 路由，删除对应路由与辅助函数
- 保持路由路径、统一 envelope、错误处理与契约完全不变

## Capabilities

纯代码结构拆分，不修改任何产品能力或 API 契约，`skip_specs: true`。

## Impact

- 新增 api/dependencies.py 与 api/routers/auth.py
- app.py 缩减约 100 行并转为挂载式组织
- OpenSpec WIKI 与问题 20 记录
