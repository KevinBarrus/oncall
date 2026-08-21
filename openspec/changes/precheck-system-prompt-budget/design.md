## Context

solution3.md 问题19：Prompt/Skill 持久化时未预检组装后长度，首次对话才遇到上下文超限。方案：端点估算 base + prompt + skills 的 token 数，超 `context_window * 0.3` 拒绝。

## Goals / Non-Goals

**Goals:**

- 持久化 Prompt/Skill 时提前拦截过大的系统提示词组合
- 正常输入不误伤（预算检查在既有内容长度校验之后）

**Non-Goals:**

- 不修改运行时预算（`ChatRuntimeContextBudget` 95% 硬限仍负责会话运行期）
- 不追踪用户会话配置变化（预检只覆盖持久化入口）

## Decisions

- 预算 = `min(int(window × 0.3), MAX_SYSTEM_PROMPT_TOKENS=30000)`——项目模板窗口为 100 万，纯 30% 分数形同虚设；绝对上限保证约束真实存在
- 按最坏情况估算（全部 Skill 完整内容已加载），与渐进式披露的运行时注入一致
- 上传 Skill 场景的 prompt 取当前会话配置（或默认）；创建/更新 Prompt 场景的 skills 取全部已上传

## Risks / Trade-offs

- [大窗口下多 Skill 受限] → 30000 tokens 上限对 100 万窗口合理（保留对话空间）；用户可精简 Skill 或拆分为按需加载
- [估算基于 tokenizer 或回退] → 与运行时 `count_tokens` 同入口，估算一致性有保证

## Migration Plan

无 schema 变更。
