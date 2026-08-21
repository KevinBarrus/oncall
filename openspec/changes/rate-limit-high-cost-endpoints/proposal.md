## Why

恶意/异常用户可快速发起大量高成本请求（chat 流、AIOps 诊断、文档上传），耗尽 LLM 配额、后台队列与存储。

## What Changes

- 新增 `super_ai/api/rate_limit.py`：进程内 per-user 滑动窗口限流器 + FastAPI 依赖工厂
- 三个高成本端点接入：chat 流（10/min）、AIOps 诊断创建（10/min）、文档上传（20/min）
- 新增错误码 `RATE_LIMIT_EXCEEDED`（429），同步 error_catalog / errors.ts / 生成 JSON / 前端用户错误文案

## Capabilities

新增 429 限流拒绝路径与错误码，`skip_specs: true`。

## Impact

- api/rate_limit.py、app.py 三个端点
- 错误码三端同步（契约测试自动校验）
- 新增限流器单元测试与 429 集成测试
