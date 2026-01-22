# Log Analyzer - 智能日志分析工具

基于插件的智能日志分析工具，支持自动化调用大模型进行运维巡查。支持 LangGraph 并发分析，提供完整的 HTTP API 接口。

## 核心特性

* 🔌 **插件化架构** (Source/Analyzer/Sink)
* 🚀 **LangGraph 并发分析** - 支持顺序和并发两种模式
* 🌐 **HTTP API** (FastAPI) - 完整的 RESTful API 接口
* 📊 **智能过滤和去重** - 大模型理解错误语义，自动分类和去重
* 💾 **多存储后端** - File/Database/MinIO
* 🔄 **健壮性保障** - 重试/超时/进度跟踪
* 🤖 **自动化运维巡查** - 定时任务、错误关联分析、修复建议

## 快速开始

### Docker 部署（推荐）

```bash
# 构建并启动
./build.sh && docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

### 本地运行

```bash
# 安装依赖
pip install -e .

# 启动服务
python -m log_analyzer.server

# 或使用命令行执行任务
python -m log_analyzer.main --task Three_Apps_Error_Analysis
```

## 项目结构

```
three_apps_diagnosis/
├── log_analyzer/              # 核心代码
│   ├── __init__.py
│   ├── config.py             # 配置加载
│   ├── server.py             # FastAPI服务器
│   ├── main.py               # 命令行入口
│   ├── task.py               # 任务执行引擎
│   └── plugins/              # 插件系统
│       ├── base.py           # 插件基类
│       ├── sources/          # 数据源插件
│       │   ├── base.py
│       │   ├── docker.py     # Docker日志源
│       │   ├── file.py       # 文件日志源
│       │   └── multi.py      # 多源聚合插件
│       ├── analyzers/        # 分析器插件
│       │   ├── base.py
│       │   └── langgraph.py  # LangGraph分析器
│       └── sinks/            # 输出插件
│           ├── base.py
│           ├── database.py   # 数据库存储
│           ├── file.py       # 文件存储
│           └── minio.py      # MinIO存储
├── config.yaml               # 配置文件
├── pyproject.toml            # Python项目配置
├── Dockerfile               # Docker镜像构建
├── docker-compose.yml       # Docker编排
├── build.sh                 # 构建脚本
├── scripts/                 # 工具脚本
│   ├── init_db.py          # 初始化数据库
│   └── check_docker.py     # 检查Docker
└── docs/                    # 文档
    └── MULTI_APP_ERROR_ANALYSIS.md
```

## 配置说明

配置文件 `config.yaml` 包含：

- **server**: 服务器配置（端口、主机）
- **database**: 数据库配置（可选）
- **tasks**: 任务列表，每个任务包含：
  - **source**: 数据源配置（docker/file/multi）
  - **analyzer**: 分析器配置（langgraph）
  - **sinks**: 输出配置（database/file/minio）

详细配置示例请参考 `config.yaml`。

## API 使用

### 查看所有任务

```bash
curl http://localhost:8000/api/tasks
```

### 触发任务执行

#### 通过API触发

```bash
# 触发名为 "Three_Apps_Error_Analysis" 的任务（使用默认时间范围）
curl -X POST http://localhost:8000/api/tasks/Three_Apps_Error_Analysis/run

# 查询最近10分钟的日志
curl -X POST "http://localhost:8000/api/tasks/Three_Apps_Error_Analysis/run?minutes_ago=10"

# 查询最近1小时的日志
curl -X POST "http://localhost:8000/api/tasks/Three_Apps_Error_Analysis/run?hours_ago=1"
```

#### 通过Docker Compose触发（推荐）

```bash
# 分析单个服务最近30分钟的错误
docker-compose --profile analyze run --rm analyze-dispatcher

# 分析指定服务最近10分钟（自定义时间）
docker-compose run --rm \
  -e CONTAINER_NAME=dispatcher \
  -e MINUTES_AGO=10 \
  log-analyzer \
  python /app/scripts/analyze_service.py

# 分析指定时间范围
docker-compose run --rm \
  -e CONTAINER_NAME=dispatcher \
  -e SINCE="2024-01-19 10:00:00" \
  -e UNTIL="2024-01-19 11:00:00" \
  log-analyzer \
  python /app/scripts/analyze_service.py
```

详细使用方法请参考 [Docker Compose使用指南](docs/DOCKER_COMPOSE_USAGE.md)

### 查询任务运行状态

```bash
# 查询任务运行 ID 为 1 的状态
curl http://localhost:8000/api/runs/1
```

### 获取分析报告

```bash
# 获取报告 ID 为 1 的内容
curl http://localhost:8000/api/reports/1
```

### 健康检查

```bash
curl http://localhost:8000/health
```

### API 文档

启动服务后，访问 <http://localhost:8000/docs> 查看 FastAPI 自动生成的交互式 API 文档。

## 核心功能

### 1. 多源数据聚合

支持同时从多个数据源收集日志：
- Docker 容器日志
- 文件日志
- SQL 查询结果
- 自定义数据源

### 2. 智能错误分析

使用大模型进行智能分析：
- 错误识别和分类
- 严重性评估
- 错误关联分析
- 根因推断
- 自动修复建议

### 3. 多存储后端

分析结果可保存到：
- 本地文件（Markdown格式）
- 数据库（SQLite/PostgreSQL）
- MinIO对象存储

### 4. 插件化架构

易于扩展：
- 自定义 Source 插件
- 自定义 Analyzer 插件
- 自定义 Sink 插件

## 使用示例

### 示例1: 多应用错误日志分析

配置文件中已包含 `Three_Apps_Error_Analysis` 任务，可以同时分析三个应用的错误日志：

```yaml
tasks:
  - name: "Three_Apps_Error_Analysis"
    source:
      name: "multi"
      params:
        sources:
          - type: "docker"
            container_name: "dispatcher"
            hours_ago: 24
            label: "dispatcher"
          # ... 更多应用
```

### 示例2: 文件日志分析

```yaml
tasks:
  - name: "File_Log_Analysis"
    source:
      name: "file"
      params:
        file_path: "logs/app.log"
```

## 开发指南

### 创建自定义插件

1. **创建 Source 插件**：继承 `AbstractSource`，实现 `collect()` 方法
2. **创建 Analyzer 插件**：继承 `AbstractAnalyzer`，实现 `analyze()` 方法
3. **创建 Sink 插件**：继承 `AbstractSink`，实现 `save()` 方法

### 运行测试

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest
```

## 依赖项

- **FastAPI**: Web框架
- **OpenAI**: LLM API客户端
- **PyYAML**: 配置文件解析
- **MinIO**: 对象存储（可选）

完整依赖列表请参考 `pyproject.toml`。

## 许可证

MIT License

---

**版本**: v0.1.1 | **更新**: 2026-01-07
