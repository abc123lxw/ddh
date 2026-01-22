# 自动监控功能说明

## 功能概述

智能运维助手现在支持**自动监控**功能，每天自动生成一次汇总报告，分析所有容器的日志。

## 配置说明

在 `config.yaml` 中添加了 `monitoring` 配置段：

```yaml
monitoring:
  enabled: true  # 是否启用自动监控
  report_interval: 86400  # 报告生成间隔（秒），默认86400秒（1天）
  containers:  # 要监控的容器列表
    - "dispatcher"
    - "agent_python"
    - "mcp_server"
  # 可以在这里添加新容器，系统会自动监控
  # - "新容器名"
  hours_ago: 24  # 每次生成报告时，分析最近N小时的日志（默认24小时）
  report_hour: 2  # 每天生成报告的时间（小时，0-23），默认凌晨2点
```

### 添加新容器

只需在 `config.yaml` 的 `monitoring.containers` 列表中添加容器名称即可：

```yaml
monitoring:
  containers:
    - "dispatcher"
    - "agent_python"
    - "mcp_server"
    - "新容器名"  # 添加这一行即可
```

系统会自动：
1. 每天在指定时间（默认凌晨2点）生成一次汇总报告
2. 分析所有配置容器的最近24小时（或配置的时间）日志
3. 生成完整的分析报告并保存到 MinIO 和本地文件

## Docker Compose 简化

### 之前（76行）
- 为每个容器单独定义服务
- 需要手动添加新服务配置
- 配置重复且冗长

### 现在（15行）
- 只有一个主服务 `log-analyzer`
- 自动监控功能内置在主服务中
- 添加新容器只需修改 `config.yaml`

### 一次性分析命令

如果需要手动触发一次性分析，使用：

```bash
docker run --rm \
  -v $(pwd)/config.yaml:/app/config.yaml:ro \
  -v $(pwd)/reports:/app/reports \
  -v /var/run/docker.sock:/var/run/docker.sock:ro \
  -e CONTAINER_NAME=容器名 \
  -e MINUTES_AGO=30 \
  log-analyzer:latest \
  python /app/scripts/analyze_service.py
```

## API 端点

### 查看监控状态

```bash
GET /api/monitoring/status
```

返回：
```json
{
  "enabled": true,
  "interval": 300,
  "containers": ["dispatcher", "agent_python", "mcp_server"],
  "minutes_ago": 10
}
```

## 工作原理

1. **启动时**：如果 `monitoring.enabled=true`，系统会启动后台监控线程
2. **等待时间**：计算下次报告生成时间（默认每天凌晨2点）
3. **定时生成**：到达指定时间后，自动生成汇总报告
4. **分析所有容器**：对所有配置的容器进行统一分析
5. **报告保存**：分析结果自动保存到 MinIO 和本地文件

## 优势

1. **零配置扩展**：添加新容器只需在配置文件中添加一行
2. **自动化运维**：无需手动触发，系统每天自动生成汇总报告
3. **资源友好**：每天只生成一次报告，不会频繁消耗 LLM API 资源
4. **简化部署**：Docker Compose 配置从 76 行减少到 15 行

## 注意事项

- 报告生成间隔默认设置为 1 天（86400 秒），适合离线环境
- 每次分析的时间范围（`hours_ago`）建议设置为 24 小时，覆盖一天的日志
- 报告生成时间（`report_hour`）建议设置在业务低峰期，如凌晨2点
- 如果需要在报告生成间隔内手动触发分析，可以通过前端界面或 API 手动触发
