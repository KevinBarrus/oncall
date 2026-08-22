## Context

solution4.md 问题3（P1）：`_worker_loop`（runtime.py:97-104）裸 while，仓储调用异常冒泡终止 worker task，后台处理静默停摆。handler 执行期异常已被 `_execute` 捕获，问题仅在框架自身的仓储调用无防护。

## Goals / Non-Goals

**Goals:**

- 仓储瞬时异常（SQLite busy、I/O）不得终止 worker 循环
- 失败有可观测事件（`background.worker.error`）+ 退避，避免空转风暴
- 状态记账失败不冒泡（租约过期后由 claim_next 自然重取，自愈）

**Non-Goals:**

- 不改变租约/心跳/重试语义与 per-kind 并发限制
- 不引入外部调度器或进程级看护（单进程内 task 级自愈足够）

## Decisions

- `_worker_loop` 双 try/except：`_claim_available` 与 `_execute` 各包一层，失败 emit `background.worker.error`（含 errorCategory + 脱敏 error）+ `_worker_backoff(consecutive_failures)` 指数退避（`min(30, 2**min(n,5))`，即 2/4/8/16/30s 封顶）；成功时重置连续失败计数
- `_execute` 的 mark_succeeded / mark_cancelled / handle_failure 各包 try/except：失败 emit `background.worker.error`（前缀标注方法名）；`background.job.completed/cancelled/failed` 状态事件仅在持久化成功时发出（`handle_failure` 失败时 `updated=None`，`final` 事件仍发但标记 final=False）
- 记账失败后的自愈路径：job 租约过期 → `claim_next` 重新领取 → 重试（受 max_attempts 约束）

## Risks / Trade-offs

- [退避期间新 job 延迟处理] → 仅瞬时故障后短暂退避，指数封顶 30s，比静默停摆到重启更优
- [重复执行语义] → mark_succeeded 失败导致 job 被重取重执行，与既有租约语义一致（handler 需幂等，同既有 retry 路径）

## Migration Plan

无 schema 变更。
