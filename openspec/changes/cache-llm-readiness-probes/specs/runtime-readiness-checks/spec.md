## MODIFIED Requirements

### Requirement: Aggregate secret-safe readiness check

后端 SHALL 暴露一个类型化的 `/ready` 端点，该端点独立检查 SQLite、Milvus、配置的 LLM 提供商以及本地 MCP 服务器，而不会暴露凭据。LLM readiness SHALL 在单个应用进程内短期缓存最近的安全检查结果，并合并并发检查；缓存过期后 MUST 重新探测。

#### Scenario: All required dependencies are ready
- **WHEN** SQLite, Milvus, 配置的 LLM 提供商以及配置的 MCP 服务器可用
- **THEN** `/ready` MUST 在可用时返回成功的 ready 结果，并包含安全组件元数据和延迟或工具计数信息。

#### Scenario: A dependency is unavailable
- **WHEN** 一个或多个必需的依赖项无法完成其 readiness 检查
- **THEN** `/ready` MUST 在保留其他组件结果的同时，对每个受影响的组件返回降级结果和安全错误，并返回非成功 HTTP 状态。

#### Scenario: 结果包含提供者配置上下文
- **WHEN** `/ready` 包含 LLM 配置上下文
- **THEN** 它 MUST 仅包含安全的提供者/模型/基础 URL 信息，以及 MUST NOT 包含一个 API 键或其他密钥。

#### Scenario: Repeated LLM probes use a short cache
- **WHEN** 同一应用进程在缓存有效期内多次执行 LLM readiness 检查
- **THEN** 系统 MUST 复用最近的安全结果，且不得重复调用 LLM。

#### Scenario: Concurrent LLM probes are coalesced
- **WHEN** 缓存为空或过期时多个请求同时执行 LLM readiness 检查
- **THEN** 系统 MUST 只执行一次 LLM 探测，其余请求 MUST 复用该结果。

#### Scenario: Cached LLM probe expires
- **WHEN** 最近 LLM readiness 结果超过缓存有效期
- **THEN** 系统 MUST 执行新的 LLM 探测并返回新的安全结果。
