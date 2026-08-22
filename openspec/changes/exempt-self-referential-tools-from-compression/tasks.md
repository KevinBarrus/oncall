## 1. 豁免名单与包装跳过

- [x] 1.1 `_NO_COMPRESSION_TOOL_NAMES` 常量 + wrapper 入口直接返回原工具

## 2. 回归测试

- [x] 2.1 read_tool_output_evidence 未被包装且返回 == evidence.content
- [x] 2.2 load_skill 未被包装且指令原文保留
- [x] 2.3 普通大输出 async 工具仍被压缩包装（防误伤）

## 3. 验证与记录

- [x] 3.1 ruff/pyright/全量 pytest（219 passed）通过
- [x] 3.2 更新 solution4.md 问题1 标记完成与 WIKI
