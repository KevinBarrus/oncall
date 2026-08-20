## Context

方案要求优先验证模型服务的 JSON Schema / function calling 支持再上 Pydantic schema；当前 Qwen OpenAI-compatible 端点未验证 `with_structured_output` 稳定支持，采用方案的第二条路径：严格 JSON-only 响应 + 受限解析 + 明确重试/降级。

## Goals / Non-Goals

**Goals:**

- 用宽容但安全的 JSON 提取替代贪婪正则，避免抓错范围
- 解析失败走明确的重试（Planner 一次）或降级（generic plan / 保留旧记忆）
- 保持现有行为与契约不变

**Non-Goals:**

- 不引入 `with_structured_output`/function calling（Qwen 兼容性未验证，避免运行时风险）
- 不改变计划结构、记忆格式或任何 API 契约

## Decisions

- 新增 `extract_json_object`：依次尝试整体 JSON、```json 代码块、括号配平提取；括号配平为字符串感知，字符串内的 `}` 不会提前截断
- `_validated_plan_with_sop_ids` 与 `_validated_memory_document` 改用 `extract_json_object`
- Planner 新增 `_plan_with_retry`：解析失败重试一次，仍失败返回空计划由调用方降级 generic plan
- 记忆压缩 prompt 明确"纯 JSON 对象、不要代码围栏"，失败保留旧记忆（既有降级）

## Risks / Trade-offs

- [宽容提取可能接受意外的 JSON] → 提取后仍按 schema 校验（steps 工具白名单、记忆 category/来源校验），不合规照样拒绝
- [未用 structured output] → 留待 Qwen 兼容性验证后按方案升级

## Migration Plan

无 schema 变更。解析路径替换后由既有与新增测试验证。
