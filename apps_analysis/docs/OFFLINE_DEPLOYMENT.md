# 离线环境部署指南

## 1. 导出镜像（在有网络的环境）

```bash
# 构建镜像
docker build -t log-analyzer:latest .

# 导出镜像为tar包
docker save log-analyzer:latest -o log-analyzer.tar

# 或者压缩版本（推荐，文件更小）
docker save log-analyzer:latest | gzip > log-analyzer.tar.gz
```

## 2. 传输到离线环境

将 `log-analyzer.tar` 或 `log-analyzer.tar.gz` 文件传输到离线环境的服务器。

## 3. 在离线环境加载镜像

```bash
# 如果是未压缩的tar包
docker load -i log-analyzer.tar

# 如果是压缩的tar包
gunzip -c log-analyzer.tar.gz | docker load

# 验证镜像是否加载成功
docker images | grep log-analyzer
```

## 4. 准备配置文件

在离线环境中，需要准备 `config.yaml` 文件，包含实际环境的配置信息。

### 必须配置的信息

1. **LLM API配置**（大模型服务）
   - `base_url`: LLM API的地址
   - `api_key`: API密钥
   - `model_name`: 模型名称

2. **Docker容器名称**（要分析的容器）
   - `container_name`: 实际运行的容器名称
   - 例如：`dispatcher`, `agent-python`, `mcp-server`

3. **MinIO配置**（如果使用MinIO存储）
   - `endpoint`: MinIO服务地址
   - `access_key`: 访问密钥
   - `secret_key`: 秘密密钥
   - `bucket_name`: 存储桶名称

## 5. 启动服务

### 方法1: 使用docker-compose

```bash
# 确保docker-compose.yml中的镜像名称正确
# 启动API服务
docker-compose up -d log-analyzer

# 查看日志
docker-compose logs -f log-analyzer
```

### 方法2: 直接使用docker命令

```bash
# 启动API服务
docker run -d \
  --name log-analyzer \
  -p 8000:8000 \
  -v $(pwd)/config.yaml:/app/config.yaml:ro \
  -v $(pwd)/reports:/app/reports \
  -v /var/run/docker.sock:/var/run/docker.sock:ro \
  -e CONFIG_PATH=/app/config.yaml \
  log-analyzer:latest

# 查看日志
docker logs -f log-analyzer
```

## 6. 测试服务

```bash
# 健康检查
curl http://localhost:8000/health

# 列出所有任务
curl http://localhost:8000/api/tasks

# 触发任务执行
curl -X POST http://localhost:8000/api/tasks/Three_Apps_Error_Analysis/run
```

## 7. 分析单个服务

```bash
# 分析dispatcher最近30分钟
docker run --rm \
  -v $(pwd)/config.yaml:/app/config.yaml:ro \
  -v $(pwd)/reports:/app/reports \
  -v /var/run/docker.sock:/var/run/docker.sock:ro \
  -e CONFIG_PATH=/app/config.yaml \
  -e CONTAINER_NAME=dispatcher \
  -e MINUTES_AGO=30 \
  log-analyzer:latest \
  python /app/scripts/analyze_service.py
```

## 注意事项

1. **Docker Socket权限**: 确保有权限访问 `/var/run/docker.sock`
2. **网络连接**: 确保容器可以访问LLM API服务（如果LLM服务在局域网内）
3. **配置文件路径**: 确保配置文件路径正确
4. **报告目录**: 确保报告目录有写权限
