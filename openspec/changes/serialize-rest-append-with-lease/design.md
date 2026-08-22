## Context

solution4.md 问题7（P2）：REST append 端点不持执行租约（与 `:stream` 不对称），也未接入限流（限流覆盖为产品决策，本地单用户低风险）。并发互斥部分与问题2 关联，问题2 已用 CAS + 去重解决；本修复补齐"append 与流式互斥"。

## Goals / Non-Goals

**Goals:**

- REST append 的 user 分支（prepare_message 含内联压缩）与流式执行互斥
- 流式执行中 append 明确失败（CHAT_SESSION_BUSY），不静默并发

**Non-Goals:**

- 不给 append 加限流（问题7 的限流部分标注为产品决策，未实施）
- 不改 assistant 分支（无压缩逻辑，纯插入不需要租约）

## Decisions

- user 分支包 `acquire_execution_lease`（token=uuid4、过期 900s 与流式一致），失败抛 `ApiErrorException("CHAT_SESSION_BUSY")`（409）；`finally` 释放
- assistant 分支保持无租约（纯 `append_message` 插入）
- 测试：直接对 app 的 repository acquire 租约后 POST user 消息，断言 409 + CHAT_SESSION_BUSY

## Risks / Trade-offs

- [append 与流式并发被阻塞] → 正是目标（流式执行中不允许并发写入压缩/预算计算）；前端已有一轮回答中禁发的交互约束

## Migration Plan

无。
