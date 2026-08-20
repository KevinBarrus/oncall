## Why

全仓 `tenant_id=owner_user_id` 传参，存在"tenant"概念与字段但实际是单用户模型，多租户未真正实现——预留了复杂度但未在文档与代码注释中明确当前租户模型，容易让阅读者误以为已支持组织级多租户。

## What Changes

- 明确当前租户模型为"单用户即单租户"：tenant 范围等于 owner 用户，owner scope 即隔离边界
- 代码注释（SopBeliefService）与 README 补充说明
- OpenSpec `authorization-and-tenant-isolation` 已明确"user ID 用作 tenant 范围，直到引入单独的组织 tenant 模型"

## Capabilities

纯说明性同步，不修改任何产品行为或隔离边界，`skip_specs: true`。

## Impact

- 代码注释与 README 说明
- OpenSpec WIKI 与问题 27 记录
