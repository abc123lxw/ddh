# Docker Compose 使用指南

## 快速开始

### 1. 启动API服务

```bash
# 启动主服务（API服务器）
docker-compose up -d log-analyzer

# 查看日志
docker-compose logs -f log-analyzer
```

### 2. 分析单个服务的错误日志

#### 方法1: 使用Docker Compose Profile

```bash
# 分析 dispatcher 服务最近30分钟的错误
docker-compose --profile analyze run --rm analyze-dispatcher

# 分析 agent-python 服务最近30分钟的错误
docker-compose --profile analyze run --rm analyze-agent-python

# 分析 mcp-server 服务最近30分钟的错误
docker-compose --profile analyze run --rm analyze-mcp-server
```

#### 方法2: 通过环境变量自定义

```bash
# 分析 dispatcher 最近10分钟
docker-compose run --rm \
  -e CONTAINER_NAME=dispatcher \
  -e MINUTES_AGO=10 \
  log-analyzer \
  python /app/scripts/analyze_service.py

# 分析 agent-python 最近1小时
docker-compose run --rm \
  -e CONTAINER_NAME=agent-python \
  -e HOURS_AGO=1 \
  log-analyzer \
  python /app/scripts/analyze_service.py

# 指定时间范围（2024-01-19 10:00:00 到 2024-01-19 11:00:00）
docker-compose run --rm \
  -e CONTAINER_NAME=dispatcher \
  -e SINCE="2024-01-19 10:00:00" \
  -e UNTIL="2024-01-19 11:00:00" \
  log-analyzer \
  python /app/scripts/analyze_service.py
```

#### 方法3: 使用预定义任务

```bash
# 使用配置文件中的任务
docker-compose run --rm \
  -e TASK=Three_Apps_Error_Analysis \
  -e MINUTES_AGO=30 \
  log-analyzer \
  python /app/scripts/analyze_service.py
```

## 环境变量说明

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `CONTAINER_NAME` | 要分析的容器名称 | `dispatcher` |
| `TASK` | 使用配置文件中的任务 | `Three_Apps_Error_Analysis` |
| `MINUTES_AGO` | 查询最近N分钟 | `30` |
| `HOURS_AGO` | 查询最近N小时 | `1` |
| `SINCE` | 开始时间 | `2024-01-19 10:00:00` |
| `UNTIL` | 结束时间 | `2024-01-19 11:00:00` |
| `CONFIG_PATH` | 配置文件路径 | `/app/config.yaml` |

## 使用示例

### 示例1: 快速检查最近30分钟

```bash
docker-compose --profile analyze run --rm analyze-dispatcher
```

### 示例2: 检查最近10分钟（紧急排查）

```bash
docker-compose run --rm \
  -e CONTAINER_NAME=dispatcher \
  -e MINUTES_AGO=10 \
  log-analyzer \
  python /app/scripts/analyze_service.py
```

### 示例3: 检查指定时间范围

```bash
# 检查今天上午10点到11点的错误
docker-compose run --rm \
  -e CONTAINER_NAME=dispatcher \
  -e SINCE="2024-01-19 10:00:00" \
  -e UNTIL="2024-01-19 11:00:00" \
  log-analyzer \
  python /app/scripts/analyze_service.py
```

### 示例4: 检查最近1小时

```bash
docker-compose run --rm \
  -e CONTAINER_NAME=agent-python \
  -e HOURS_AGO=1 \
  log-analyzer \
  python /app/scripts/analyze_service.py
```

## 查看报告

分析完成后，报告会保存在 `./reports/` 目录下：

```bash
# 查看报告文件
ls -lh reports/

# 查看最新报告
ls -t reports/*.md | head -1 | xargs cat
```

## 定时任务

可以使用cron或systemd timer来定时执行：

### 使用cron

```bash
# 编辑crontab
crontab -e

# 添加定时任务（每天上午8点分析dispatcher最近24小时）
0 8 * * * cd /path/to/three_apps_diagnosis && docker-compose --profile analyze run --rm analyze-dispatcher
```

### 使用Docker Compose的depends_on

如果需要分析完成后自动清理，可以创建一个一次性服务：

```yaml
analyze-once:
  build: .
  volumes:
    - ./config.yaml:/app/config.yaml:ro
    - ./reports:/app/reports
    - /var/run/docker.sock:/var/run/docker.sock:ro
  environment:
    - CONTAINER_NAME=dispatcher
    - MINUTES_AGO=30
  command: python /app/scripts/analyze_service.py
  restart: "no"  # 只执行一次
```

## 注意事项

1. **Docker Socket**: 需要挂载 `/var/run/docker.sock` 才能访问其他容器的日志
2. **网络**: 分析服务需要和主服务在同一网络，或者使用host网络
3. **权限**: 确保有权限访问Docker socket
4. **时间格式**: 时间格式支持 `YYYY-MM-DD HH:MM:SS` 或 `YYYY-MM-DDTHH:MM:SS`

## 故障排查

### 问题1: 无法访问Docker socket

```bash
# 检查权限
ls -l /var/run/docker.sock

# 可能需要添加用户到docker组
sudo usermod -aG docker $USER
```

### 问题2: 容器名称不存在

```bash
# 查看所有运行的容器
docker ps

# 使用正确的容器名称
docker-compose run --rm \
  -e CONTAINER_NAME=正确的容器名 \
  log-analyzer \
  python /app/scripts/analyze_service.py
```

### 问题3: 报告未生成

检查：
- 是否有错误日志
- 报告目录是否有写权限
- 查看容器日志: `docker-compose logs analyze-dispatcher`
