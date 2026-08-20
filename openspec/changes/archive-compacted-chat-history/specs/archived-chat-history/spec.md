## Purpose

将已经被会话记忆摘要覆盖的原始聊天消息移出运行时热路径，同时继续按 owner 和会话范围保留可追溯历史与结构化元数据。

## ADDED Requirements

### Requirement: Compacted chat history is archived
系统 SHALL 在成功生成覆盖一批历史消息的记忆摘要后归档该批原始消息；归档 MUST 保留 owner、会话、消息 ID、角色、内容、元数据、创建时间和归档时间。

#### Scenario: Summary archives compacted messages
- **WHEN** 会话记忆摘要成功覆盖一批历史消息
- **THEN** 系统 MUST 将该批消息从运行时热历史移至 owner 和会话范围的归档历史

### Requirement: Archived history remains traceable
系统 SHALL 在读取、清除或删除会话时处理归档历史，不得因归档丢失 user 的消息原文、引用或工具元数据。

#### Scenario: User reads a session with archived messages
- **WHEN** user 读取包含归档消息的会话
- **THEN** 系统 MUST 按消息创建顺序返回归档与活跃消息

#### Scenario: User clears or deletes an archived session
- **WHEN** user 清除或删除包含归档消息的会话
- **THEN** 系统 MUST 同步删除该 user 和会话范围的归档消息
