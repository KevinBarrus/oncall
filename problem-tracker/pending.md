# 待后续评估的问题

以下问题来自第一轮初始评估，但没有进入第一轮修复。它们不占用 `problem2.md`；只有完成新一轮评估后，才把新发现的问题整理进 `problem2.md`，对应方案写入 `solution2.md`。

## 评测系统

2. 评测数据集规模较小，当前结果不能支持系统级泛化结论。
3. 确定性指标依赖 token overlap 自动生成相关性标签，存在循环依赖。
4. LLM Judge 失败时返回 0.5，无法区分真实分数和评测异常。
5. Clean-room baseline 实际是 answer-injection sanity check，不是严格的真实文档生成上界。

## SOP 学习系统

6. SOP belief 使用用户目录 JSON，绕过 owner/tenant、Repository、事务和统一审计边界。
7. SOP 成功归因范围过宽，将被检索但未实际使用的 SOP 也纳入结果更新。
8. 人工反馈没有幂等约束，重复点击或请求重放会重复改变后验概率。

## 后续原则

- 完成第一轮代码验证后，再进行一次独立评估。
- 新评估发现的问题统一写入 `problem2.md`，不要继续拆成 `problem3.md`、`problem4.md`。
- `solution2.md` 按“问题1方案、问题2方案……”对应 `problem2.md`。
