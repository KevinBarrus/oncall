## 1. 依赖核对

- [x] 1.1 确认重 ML 依赖已全部移出运行时 dependencies
- [x] 1.2 核对剩余依赖归属（rank-bm25 由 src 使用，jieba 为轻量评测依赖）

## 2. CI 分层

- [x] 2.1 确认 CI 主门禁不安装 eval group，评测 job 显式安装

## 3. 记录

- [x] 3.1 更新问题 21 方案与 WIKI
