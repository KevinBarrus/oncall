# 可观测性与监控告警最佳实践

## SLI / SLO / SLA 概念

### SLI（Service Level Indicator）

SLI 是服务质量的量化指标。常见 SLI 包括：

- **可用性**：成功请求数 / 总请求数，通常以百分比表示（如 99.9%）
- **延迟**：请求响应时间的 P50、P95、P99 分位数
- **错误率**：错误响应数 / 总请求数
- **吞吐量**：每秒处理的请求数（QPS/RPS）

对于不同类型的服务，应该选择不同的 SLI：
- HTTP API 服务：关注状态码 5xx 比例、P99 延迟
- 消息队列消费者：关注消费延迟、消息堆积量
- 数据库：关注查询延迟、连接数饱和度

### SLO（Service Level Objective）

SLO 是基于 SLI 设定的内部目标值。例如：
- 99.9% 的请求在 500ms 内完成（月度统计）
- 可用性达到 99.95%（季度统计）
- 错误率低于 0.1%

SLO 设定原则：
1. 应该比 SLA 更严格，留出 buffer。如果 SLA 承诺 99.9%，SLO 应该设 99.95%
2. 从用户视角出发，只度量用户可感知的指标
3. 不要追求 100%——完美没有容错空间，成本极高
4. 使用错误预算（Error Budget）机制：1 - SLO = 允许的错误量

### SLA（Service Level Agreement）

SLA 是对外承诺的服务等级协议，通常是商业合同的一部分。未达成 SLA 会有经济赔偿。SLA 通常比 SLO 宽松，比如 SLA 承诺 99.9%，内部 SLO 设 99.95%。

## 错误预算机制

错误预算是 1 - SLO。如果 30 天窗口内 SLO 是 99.9%，错误预算就是 43 分钟。

错误预算耗尽时的策略：
- 冻结所有功能发布
- 将工程资源投入稳定性改进
- 直到预算恢复（新的统计窗口或通过修复降低了错误率）

## Prometheus 告警规则设计

### 服务可用性监控

```yaml
groups:
  - name: service_availability
    rules:
      - alert: ServiceDown
        expr: up == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "服务 {{ $labels.job }} 不可达"
          description: "服务 {{ $labels.job }} 已宕机超过 2 分钟，请立即排查。"
```

### 告警分级

| 级别 | 响应时间 | 通知方式 | 举例 |
|------|----------|----------|------|
| Critical | 5 分钟内 | 电话 + 即时通讯 | 核心服务宕机、数据库不可用 |
| Warning | 30 分钟内 | 即时通讯 | CPU > 90%、磁盘 > 85% |
| Info | 工作时间 | 邮件/Ticket | 证书即将过期、配置变更通知 |

### 告警收敛与抑制

使用 Alertmanager 的 route 配置实现告警分组：

```yaml
route:
  group_by: ['alertname', 'service']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
```

inhibit_rules 实现告警抑制，例如机器宕机时抑制该机器上所有应用告警：

```yaml
inhibit_rules:
  - source_match:
      alertname: NodeDown
    target_match_re:
      alertname: '.*'
    equal: ['instance']
```

## 故障复盘（Postmortem）

### 复盘流程

1. **时间线梳理**：按时间顺序记录故障从发生到完全恢复的所有关键事件，精确到分钟
2. **影响评估**：统计受影响用户数、持续时长、业务损失
3. **根因分析**：使用 5-Why 方法追溯根本原因，区分直接原因和系统性问题
4. **响应评估**：告警是否及时触发、人员是否及时响应、处理流程是否顺畅
5. **Action Items 制定**：每项必须是可执行、有负责人和截止日期的具体任务
6. **知识沉淀**：将复盘文档归档到知识库，建立故障模式库

### 复盘原则

- **Blameless**：不对个人追责，关注流程和系统的改进
- **实事求是**：基于数据和时间线，不做主观臆断
- **闭环跟踪**：每个 Action Item 必须有明确的负责人、截止日期和验证标准
