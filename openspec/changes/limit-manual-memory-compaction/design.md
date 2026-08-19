## Context

现有 `set_mode(..., manual)` 和 `memory:compact` 会调用 `compact()`，后者循环调用 LLM，直到所有未压缩消息处理完。既有 `chat_memory_compaction` durable job 已经只调用一次 `compact_once()`，并具备 owner 作用域、重试与任务查询能力。

## Goals / Non-Goals

**Goals:**

- 复用既有任务运行时，使两个手动入口立即返回
- 在响应中暴露该任务，前端可使用既有任务 API 跟踪状态
- 保持每个 job 仅压缩一个预算内批次

**Non-Goals:**

- 不新增队列、数据表或前端轮询机制
- 不改变自动压缩和硬限同步兜底

## Decisions

- 将任务投递函数改为返回已有 `BackgroundJobRecord`。这是最小的现有类型复用；不新增任务 DTO 或并行任务服务
- `set_mode` 只负责更新模式和刷新上下文使用量；API 层在 manual 入口投递任务。这样模式服务不依赖 HTTP/job 表示，同时显式压缩入口共享同一投递路径
- 两个响应返回 `{ session, job }`。替代方案是仅返回 session 并让前端按会话扫描任务；后者不能可靠定位刚创建的任务

## Risks / Trade-offs

- [重复点击会创建多个任务] → 每个任务仍只处理一个批次；后续若出现实际重复负载，再为会话增加去重约束
- [任务尚未运行时会话占用未降低] → 响应明确提供任务状态，前端可沿用既有任务查询能力

## Migration Plan

1. 部署后新请求异步返回任务，原始消息和已有摘要均不迁移
2. 回滚仅恢复同步调用路径；持久化任务可按既有取消/重试语义处理
