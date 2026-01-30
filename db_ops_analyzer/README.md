# 数据库智能运维分析工具

基于大模型的数据库智能运维工具，支持性能分析、慢查询分析、配置审计、容量规划等功能。

## 核心特性

* 🔌 **插件化架构** (Source/Analyzer/Sink) - 复用日志分析工具的成熟架构
* 🗄️ **多数据库支持** - MySQL、PostgreSQL、Redis、MongoDB等
* 🚀 **智能分析** - 使用大模型进行深度分析和优化建议
* 📊 **性能分析** - 慢查询分析、索引优化、连接池分析
* 🔒 **安全审计** - 配置安全检查、权限审计
* 💾 **容量规划** - 存储增长预测、资源使用分析
* 🌐 **HTTP API** - 完整的 RESTful API 接口
* 🤖 **自动化巡检** - 定时任务、自动报告生成

## 功能模块

### 1. 性能分析
- 慢查询识别和分析
- 索引使用情况分析
- 连接池状态分析
- 锁等待分析
- 性能瓶颈定位

### 2. 配置审计
- 配置参数检查
- 安全配置审计
- 最佳实践检查
- 配置优化建议

### 3. 容量规划
- 存储空间分析
- 数据增长趋势预测
- 资源使用分析
- 扩容建议

### 4. 安全审计
- 用户权限审计
- 敏感数据识别
- 访问模式分析
- 安全漏洞检测

## 快速开始

### 安装依赖

```bash
pip install -e .
```

### 配置

复制 `config.yaml.template` 为 `config.yaml`，配置数据库连接信息。

### 运行

```bash
# 启动服务
python -m db_ops_analyzer.server

# 或使用命令行
python -m db_ops_analyzer.main --task MySQL_Performance_Analysis
```

## 项目结构

```
db_ops_analyzer/
├── db_ops_analyzer/          # 核心代码
│   ├── __init__.py
│   ├── config.py            # 配置加载
│   ├── server.py            # FastAPI服务器
│   ├── main.py              # 命令行入口
│   ├── task.py              # 任务执行引擎
│   └── plugins/             # 插件系统
│       ├── sources/         # 数据源插件
│       │   ├── mysql.py    # MySQL数据源
│       │   ├── postgresql.py
│       │   ├── redis.py
│       │   └── mongodb.py
│       ├── analyzers/       # 分析器插件
│       │   └── langgraph.py # LLM分析器
│       └── sinks/           # 输出插件
│           ├── file.py
│           ├── database.py
│           └── minio.py
├── config.yaml              # 配置文件
├── pyproject.toml           # 项目配置
└── README.md
```

## 使用示例

### MySQL 性能分析

```yaml
tasks:
  - name: "MySQL_Performance_Analysis"
    source:
      name: "mysql"
      params:
        host: "localhost"
        port: 3306
        user: "root"
        password: "password"
        database: "mydb"
        collect_slow_queries: true
        collect_processlist: true
        collect_status: true
    
    analyzer:
      name: "langgraph"
      params:
        base_url: "http://your-llm-server/v1"
        api_key: "your-api-key"
        model_name: "your-model"
    
    sinks:
      - name: "file"
        params:
          output_path: "reports/mysql_performance_{{timestamp}}.md"
```

## 许可证

MIT License
