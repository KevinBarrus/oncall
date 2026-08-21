## Context

solution3.md 问题6：批量任务并发写 SQLite 触发 `SQLITE_BUSY`、单一 kind 占满 worker。已有 `concurrency`（worker 数）全局限制，缺失的是按任务类型的并发上限。

## Goals / Non-Goals

**Goals:**

- 每种任务类型（kind）可配置独立并发上限，避免单一 kind 占满全部 worker
- 检查槽位 → 领取 → 计数的临界区无竞态

**Non-Goals:**

- 不改变 worker 数量语义（`concurrency` 仍控制并行 worker 数）
- 不引入跨进程限流（项目为单进程运行；多进程时 SQLite 租约仍保证任务不被重复领取）

## Decisions

- `claim_next` 增加可选 `kind` 参数：SQLite 实现按 `kind` 过滤，空闲槽位才领取
- `_claim_available` 遍历已注册 kinds，跳过达上限的 kind；用 `asyncio.Lock` 串行化"检查-领取-计数"，消除多 worker 竞态（两个 worker 同时通过检查都领取同类任务的场景）
- 槽位在 `_execute` 的 `finally` 与 handler 缺失分支释放
- app.py 为写密集/长任务配置每 kind 上限 1

## Risks / Trade-offs

- [单进程内计数] → 多进程部署时计数仅对本进程有效；SQLite 租约仍防重复领取，kind 上限退化为尽力而为
- [Lock 串行化领取] → 领取是快速 DB 操作，多个 worker 竞争时仅短暂等待，不影响执行吞吐

## Migration Plan

无 schema 变更。`claim_next` 新增参数为向后兼容（默认 `None` 保持原行为）。
