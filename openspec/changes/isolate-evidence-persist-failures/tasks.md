## 1. evidence 写入兜底

- [x] 1.1 str 与 dict 两条路径 create 包 try/except，失败仅 emit 事件

## 2. 回归测试

- [x] 2.1 create 抛错时工具调用仍返回压缩摘要且无 evidenceId

## 3. 验证与记录

- [x] 3.1 ruff/pyright/全量 pytest（230 passed）通过
- [x] 3.2 更新 solution4.md 问题12 标记完成与 WIKI
