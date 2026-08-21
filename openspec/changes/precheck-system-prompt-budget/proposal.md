## Why

用户 Prompt + 多个 Skill（`load_skill` 后注入完整内容）可能使 system prompt 超出上下文窗口，首次对话才暴露。

## What Changes

- 新增 `estimate_system_prompt_tokens`：按最坏情况估算 base + 用户提示词 + 全部 Skill 完整内容的 token 数
- `POST/PUT /chat/prompts`、`POST /chat/skills` 持久化前预检：超过 `min(window × 30%, 30000)` 预算拒绝并提示
- 预算取比例与绝对上限的较小者——防止超大窗口（100 万）下 30% 分数形同虚设

## Capabilities

纯校验增强，API 行为为追加式（新增 400 拒绝路径），`skip_specs: true`。

## Impact

- chat/configuration.py 估算函数与预算常量
- api/app.py 三个端点接入预检
- 新增预算拒绝 API 测试
