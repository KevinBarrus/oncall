## Why

第三轮验收将 Milvus tenant 作用域过滤列为确认项（原报告标 P0 但复核未找到缺口）：`search/list/delete` 均强制显式 `tenant_id` 作用域，需以测试固化"跨租户不可见"边界，防止未来新增操作遗漏。

## What Changes

- 新增租户 filter 互斥测试：不同 tenant 的 filter 不包含对方租户值
- 新增 filter 转义测试：租户/知识库值含引号时安全转义
- 复核确认：全部 Milvus 数据访问操作（search/list/delete）均要求显式 tenant 作用域，无 `count_chunks` 等遗漏操作

## Capabilities

纯测试固化，不修改任何运行时行为，`skip_specs: true`。

## Impact

- tests/test_milvus_vector_store.py 新增边界测试
- 确认项结论：作用域过滤无缺口
