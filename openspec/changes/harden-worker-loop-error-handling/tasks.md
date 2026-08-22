## 1. worker 循环防护

- [x] 1.1 `_worker_loop` 双 try/except + `background.worker.error` 事件 + 指数退避
- [x] 1.2 `_execute` 状态记账（mark_succeeded/mark_cancelled/handle_failure）各自兜底

## 2. 回归测试

- [x] 2.1 claim_next 抛错 → worker 存活并继续处理后续 job
- [x] 2.2 mark_succeeded 抛错 → worker 存活（job 走租约重取）
- [x] 2.3 handler 异常 + handle_failure 抛错 → worker 存活

## 3. 验证与记录

- [x] 3.1 ruff/pyright/全量 pytest（222 passed）通过
- [x] 3.2 更新 solution4.md 问题3 标记完成与 WIKI
