## Context

`_validated_memory_document` 只做结构校验：JSON 合法性、summary ≤1200 字、category 白名单、sourceMessageIds 归属。模型可以在结构合法的情况下编造数字、错误码或与原文无关的决策、待办，当前系统无法识别。

## Goals / Non-Goals

**Goals:**

- 用确定性规则校验摘要声称可追溯到压缩原文，不引入额外 LLM 调用
- 数字与数字形式错误码必须出现在原文；decision/todo 条目必须与原文共享字面证据
- 校验失败通过既有异常路径保留上一版记忆，不覆盖已有摘要

**Non-Goals:**

- 不引入 LLM-as-judge 或低频抽检复核；这类成本与复杂度留待出现明确需求时单独评估
- 不做语义级忠实性判定；仅覆盖可确定性规则化的数字、错误码与行动条目字面证据

## Decisions

- 新增 `_validate_memory_fidelity(memory, source_text)`，在 `_validated_memory_document` 结构校验之后执行，职责单一
- 数字比对使用 `\d+(?:\.\d+)?` 提取，数字形式错误码（如 500、503）由数字规则覆盖
- decision/todo 条目要求与原文共享至少一个长度≥2 的非数字连续片段，捕获完全脱离原文的行动条目
- 新增 `MemoryFidelityError` 专用异常，与结构校验失败区分，便于日志与测试定位

## Risks / Trade-offs

- [字面证据检查可能误拒合法改写] → 只作用于 decision/todo 且阈值为长度≥2 的共享片段，误拒时为安全失败（保留旧记忆，不产生错误上下文）
- [数字比对无法捕获同义改写] → 属已知局限；更细粒度语义校验留待低频 Judge 抽检需求明确后评估

## Migration Plan

无数据库 schema 变更；仅聊天记忆服务运行时校验路径变更。回滚即恢复原结构校验行为。
