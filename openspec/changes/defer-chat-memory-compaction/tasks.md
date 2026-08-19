## 1. Chat memory behavior

- [x] 1.1 将自动阈值压缩改为后台投递，并保留硬限的一次同步超时兜底
- [x] 1.2 为摘要调用和结构校验失败增加保留原记忆的降级与可观测事件

## 2. Durable runtime integration

- [x] 2.1 注册 owner 范围的聊天记忆压缩 job，并复用既有任务生命周期

## 3. Verification and records

- [x] 3.1 补充自动投递、失败降级和硬限兜底回归测试
- [x] 3.2 更新问题 3 的解决方案并运行 OpenSpec、Ruff、Pyright、目标 pytest 和迁移验证
