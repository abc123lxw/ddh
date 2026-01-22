# 按时间范围查询日志

## 功能说明

系统支持按时间范围查询日志，可以指定查询最近N分钟或N小时的日志。

## 使用方法

### 方法1: 通过API动态指定时间范围

在调用API时，可以通过查询参数指定时间范围：

```bash
# 查询最近10分钟的日志
curl -X POST "http://localhost:8000/api/tasks/Three_Apps_Error_Analysis/run?minutes_ago=10"

# 查询最近1小时的日志
curl -X POST "http://localhost:8000/api/tasks/Three_Apps_Error_Analysis/run?hours_ago=1"

# 查询最近30分钟（minutes_ago优先级更高）
curl -X POST "http://localhost:8000/api/tasks/Three_Apps_Error_Analysis/run?minutes_ago=30&hours_ago=2"
# 注意：如果同时指定，minutes_ago会覆盖hours_ago
```

### 方法2: 在配置文件中指定

在 `config.yaml` 中直接配置时间范围：

```yaml
tasks:
  - name: "Quick_Check_10min"
    source:
      name: "multi"
      params:
        sources:
          - type: "docker"
            container_name: "dispatcher"
            minutes_ago: 10  # 最近10分钟
            label: "dispatcher"
```

## 参数说明

### DockerSource 时间参数

- `minutes_ago`: 查询最近N分钟的日志（优先级最高）
- `hours_ago`: 查询最近N小时的日志（如果未指定minutes_ago）

**注意**：
- 如果同时指定 `minutes_ago` 和 `hours_ago`，`minutes_ago` 会优先使用
- 如果都不指定，默认查询最近24小时

## 使用示例

### 示例1: 快速检查最近10分钟的错误

```bash
# 通过API调用
curl -X POST "http://localhost:8000/api/tasks/Three_Apps_Error_Analysis/run?minutes_ago=10"

# 响应
{
  "message": "任务已启动",
  "run_id": 1,
  "task_name": "Three_Apps_Error_Analysis",
  "time_range": {
    "minutes_ago": 10,
    "hours_ago": null
  }
}
```

### 示例2: 检查最近1小时

```bash
curl -X POST "http://localhost:8000/api/tasks/Three_Apps_Error_Analysis/run?hours_ago=1"
```

### 示例3: 检查最近5分钟（紧急排查）

```bash
curl -X POST "http://localhost:8000/api/tasks/Three_Apps_Error_Analysis/run?minutes_ago=5"
```

## 常见时间范围

| 时间范围 | minutes_ago | hours_ago |
|---------|-------------|-----------|
| 最近5分钟 | 5 | - |
| 最近10分钟 | 10 | - |
| 最近30分钟 | 30 | - |
| 最近1小时 | - | 1 |
| 最近6小时 | - | 6 |
| 最近24小时 | - | 24（默认）|

## 注意事项

1. **API优先级**：通过API参数指定的时间范围会临时覆盖配置文件中的设置，但不会永久修改配置文件
2. **性能考虑**：查询时间范围越大，收集的日志越多，分析时间越长
3. **Docker限制**：Docker日志查询依赖于Docker的日志存储机制，过旧日志可能无法查询

## 配置示例

在 `config.yaml` 中已经包含了一个快速检查任务：

```yaml
- name: "Quick_Check_10min"
  source:
    name: "multi"
    params:
      sources:
        - type: "docker"
          container_name: "dispatcher"
          minutes_ago: 10
          label: "dispatcher"
```

可以直接使用这个任务，或通过API动态修改时间范围。
