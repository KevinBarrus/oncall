# 问题 11：SOP belief 文件绕过租户和持久化边界

## 评估

确认成立，高优先级。

`sop_belief.py` 使用用户目录下的 `~/.oncall/sop_beliefs.json` 保存 belief state，不属于 SQLite/Alembic/Repository 体系，也没有完整的 owner、tenant、文档版本和统一审计边界。

## 影响

不同用户可能共享成功率；多进程写入可能互相覆盖；非原子写入可能损坏文件；无法稳定按知识库、文档版本和任务追溯或备份。

## 结论

与项目现有 owner/tenant 隔离原则冲突，是生产化前必须处理的问题。
