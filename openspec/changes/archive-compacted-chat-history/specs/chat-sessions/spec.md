## MODIFIED Requirements

### Requirement: Authenticated chat session lifecycle
系统 SHALL 允许经过身份验证的 users 从后端 APIs 创建、列出、读取、清除和删除他们自己的聊天会话；读取会话 MUST 合并其归档与活跃消息，清除或删除会话 MUST 同步处理两类消息。

#### Scenario: 创建聊天会话
- **WHEN** 已认证的 user 可使用可选标题创建聊天会话
- **THEN** 后端 MUST 将会话持久化到 SQLite 中，使用当前 user 的 owner ID 并返回已创建的会话。

#### Scenario: List chat sessions
- **WHEN** 已认证的 user 列出聊天会话
- **THEN** 后端 MUST 仅返回该 user 的会话，并按最近更新的顺序排列。

#### Scenario: Read chat session history
- **WHEN** 已认证的 user 读取其其中一个聊天会话
- **THEN** 后端 MUST 按照创建顺序返回会话及其持久化的归档和活跃消息。

#### Scenario: Clear chat session history
- **WHEN** 已认证的 user 可清除其聊天会话之一
- **THEN** 后端 MUST 在保留会话记录可访问的同时，删除该会话的活跃和归档消息。

#### Scenario: Delete chat session
- **WHEN** 已认证的 user 删除其其中一个聊天会话
- **THEN** 后端 MUST 从 user 的可访问会话列表中删除该会话及其活跃和归档消息
