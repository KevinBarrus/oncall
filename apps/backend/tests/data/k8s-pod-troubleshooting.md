# Kubernetes Pod 故障排查手册

## CrashLoopBackOff 排查

Pod 处于 CrashLoopBackOff 状态表示容器启动后立即崩溃，Kubernetes 不断尝试重启但每次都以失败告终。

### 排查步骤

1. **查看 Pod 详细信息**：`kubectl describe pod <pod-name>`，重点关注 Events 部分的退出原因和退出码。常见退出码：137（OOMKilled）、1（应用错误）、143（SIGTERM）。
2. **查看崩溃容器日志**：`kubectl logs <pod-name> --previous`，这个命令可以查看上一次崩溃容器的标准输出。如果容器启动后瞬间崩溃，当前日志可能为空，必须用 `--previous`。
3. **检查启动命令**：验证 Dockerfile 中的 CMD/ENTRYPOINT 是否正确。如果使用了 shell 语法但镜像中没有对应的 shell，启动会立即失败。
4. **检查资源限制**：`kubectl describe pod` 中的 Limits 和 Requests。如果 memory limit 设置过低（如 64Mi），Java 应用可能无法启动。确认是否存在 OOMKilled。
5. **检查健康检查探针**：liveness probe 配置不当可能导致容器被误杀。确认 initialDelaySeconds 足够长（至少 30-60 秒），periodSeconds 不要太短。
6. **检查 ConfigMap/Secret**：如果应用依赖 ConfigMap 中的配置文件，确认 ConfigMap 已正确创建并挂载。Secret 中的敏感信息（数据库密码等）是否正确。
7. **检查镜像问题**：确认镜像名称和标签是否正确，imagePullPolicy 设置（Always/IfNotPresent）是否符合预期。

### 快速诊断命令

```bash
# 查看 Pod 状态
kubectl get pod <pod-name> -o yaml

# 查看退出码
kubectl describe pod <pod-name> | grep -A5 "Last State"

# 查看崩溃前日志
kubectl logs <pod-name> --previous --tail=50

# 查看资源使用
kubectl top pod <pod-name>
```

## Pod Pending 排查

Pod 长时间处于 Pending 状态，通常是调度失败。

### 常见原因

1. **资源不足**：集群中所有节点的可用 CPU/内存不足以满足 Pod 的 requests。使用 `kubectl describe pod` 查看 Events 中是否有 "Insufficient cpu" 或 "Insufficient memory"。
2. **节点选择器不匹配**：nodeSelector 或 nodeAffinity 规则导致没有符合条件的节点。
3. **污点和容忍度**：节点有 taint 但 Pod 没有对应的 toleration。
4. **PVC 绑定失败**：如果 Pod 依赖 PersistentVolumeClaim，而 PVC 无法绑定到 PV，Pod 会一直 Pending。

## ImagePullBackOff 排查

1. 检查镜像名称是否正确（仓库地址、镜像名、标签）。
2. 如果是私有仓库，确认 imagePullSecrets 已正确配置。
3. 使用 `docker pull <image>` 在本地验证镜像是否可拉取。
4. 检查网络策略是否阻止了节点访问镜像仓库。
