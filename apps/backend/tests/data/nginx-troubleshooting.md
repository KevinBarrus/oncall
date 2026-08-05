# Nginx 故障排查手册

## Nginx 502 Bad Gateway 排查

Nginx 返回 502 Bad Gateway 表示作为反向代理时，无法从上游服务器获取有效响应。

### 排查步骤

1. **检查后端服务状态**：使用 `systemctl status <service>` 或 `ps aux | grep <process>` 确认后端进程是否存活。
2. **检查 Nginx 错误日志**：`tail -f /var/log/nginx/error.log`，查看 "upstream" 相关的连接失败信息。常见错误包括 "connect() failed (111: Connection refused)" 和 "upstream timed out (110: Connection timed out)"。
3. **验证 upstream 配置**：检查 nginx.conf 中的 upstream 块，确认后端服务器地址和端口正确。
4. **检查连接数限制**：后端服务的连接数可能达到上限，需要调整 nginx 的 worker_connections 或后端应用服务器的连接池大小。
5. **系统资源检查**：使用 `top`、`free -h`、`df -h` 确认 CPU、内存、磁盘没有耗尽。使用 `ulimit -n` 检查文件描述符限制。
6. **PHP-FPM 场景**：如果是 PHP 应用，检查 php-fpm 进程是否存活（`systemctl status php-fpm`），以及 socket 文件权限是否正确。

### 常见原因速查

| 现象 | 可能原因 | 快速检查 |
|------|----------|----------|
| connect() refused | 后端服务未启动 | systemctl status |
| upstream timed out | 后端响应超时 | 调整 proxy_read_timeout |
| no live upstreams | 所有后端不可用 | 检查 upstream 配置 |
| SSL 握手失败 | 后端证书问题 | 检查 proxy_ssl_verify |

## Nginx 性能优化

### Worker 配置

```
worker_processes auto;
worker_connections 4096;
```

worker_processes 设为 auto 让 Nginx 自动匹配 CPU 核心数。每个 worker 的 connections 乘以 worker 数就是最大并发连接数。

### 缓冲区优化

```
proxy_buffer_size 16k;
proxy_buffers 4 64k;
proxy_busy_buffers_size 128k;
```

增大缓冲区可以减少磁盘 I/O，提升响应速度。

### 静态文件缓存

```
location ~* \.(jpg|jpeg|png|gif|ico|css|js)$ {
    expires 30d;
    add_header Cache-Control "public, immutable";
}
```

为静态资源配置长期缓存，减少重复请求。
