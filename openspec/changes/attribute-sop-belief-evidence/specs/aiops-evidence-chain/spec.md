## ADDED Requirements

### Requirement: SOP 候选与归因信息纳入诊断证据链

系统 SHALL 在 owner 范围内保存每次诊断的 SOP 候选曝光及实际归因信息，使证据链能说明候选是否参与了最终诊断。

#### Scenario: 读取含 SOP 候选的诊断证据链
- **WHEN** 授权用户读取其诊断的证据链
- **THEN** 系统返回 SOP 候选曝光及其归因阶段
- **AND** 不向其他 owner 泄露该诊断的候选或归因信息
