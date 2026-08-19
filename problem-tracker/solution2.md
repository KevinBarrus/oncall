# 第二轮修复方案与实施记录

## 问题1方案：增加真实聊天链路评测

- 在 `tests/ragas_evaluation.py` 增加 `--e2e` 入口。
- 通过真实 HTTP API 注册或登录评测账号。
- 创建真实聊天会话，调用 `/chat/sessions/{id}/messages:stream`。
- 解析真实 SSE，统计回答、引用、工具调用、完成事件和端到端延迟。
- 使用真实聊天链路返回的引用作为评测上下文，并复用现有 LLM Judge 指标。
- 将结果写入 `endToEnd`，与离线策略结果分开，避免混淆两类结论。
- 使用 `RAGAS_API_BASE_URL` 支持切换被测后端地址。

### 使用方式

```bash
cd apps/backend
uv run python tests/ragas_evaluation.py --e2e --limit 5
```

默认不启用端到端评测，避免普通离线评测额外消耗真实 Agent 和模型调用；显式传入 `--e2e` 后才执行。

### 验证结果

- `UV_CACHE_DIR=/tmp/oncall-uv-cache uv run pytest tests/ragas_evaluation.py -q`：通过。
- `python3 -m py_compile tests/ragas_evaluation.py`：通过。
- Pyright 仍存在该脚本原有类型问题，本次未新增相关类型错误。
