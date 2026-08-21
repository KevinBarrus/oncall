## 1. 估算与预算

- [x] 1.1 `estimate_system_prompt_tokens`（base + prompt + 全部 Skill 完整内容）
- [x] 1.2 预算 = min(窗口×30%, 30000)

## 2. 端点接入

- [x] 2.1 POST/PUT /chat/prompts 预检
- [x] 2.2 POST /chat/skills 预检（含新 Skill）

## 3. 验证与记录

- [x] 3.1 API 测试：多 Skill 累积超预算拒绝、正常输入接受
- [x] 3.2 全量 ruff/pyright/pytest 通过；更新问题 19 记录与 WIKI
