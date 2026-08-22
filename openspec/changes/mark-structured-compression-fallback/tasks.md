## 1. 结构化路径标记

- [x] 1.1 复用 tool_output_compression_metadata + sampled_fallback 补 compressionFailed

## 2. 回归测试

- [x] 2.1 降级路径带 compressionFailed=True；llm_summary 成功路径不带标记

## 3. 验证与记录

- [x] 3.1 ruff/pyright/全量 pytest（225 passed）通过
- [x] 3.2 更新 solution4.md 问题4 标记完成与 WIKI
