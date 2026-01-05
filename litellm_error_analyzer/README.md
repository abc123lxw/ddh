# LiteLLM 错误日志分析工具

一个用于查询和分析 LiteLLM 错误日志的完整工具集，支持从 PostgreSQL 数据库查询错误日志，并使用大模型进行智能分析。

## 📋 目录

- [项目概述](#项目概述)
- [代码实现原理](#代码实现原理)
- [环境准备](#环境准备)
- [配置说明](#配置说明)
- [使用方法](#使用方法)
- [代码架构详解](#代码架构详解)
- [常见问题](#常见问题)
- [操作文档](#操作文档)

---

## 📖 项目概述

### 功能特性

1. **错误日志查询**
   - 支持时间范围筛选（最近 N 天或指定时间范围）
   - 支持按 Key Alias/Name 筛选
   - 支持按模型名称筛选
   - 从 PostgreSQL 数据库查询（通过 Docker exec）

2. **智能分析**
   - 自动提取错误关键信息
   - 支持调用大模型 API 进行深度分析
   - 生成结构化分析报告

3. **结果保存**
   - 自动按日期创建输出目录
   - 保存完整日志、分析日志、LLM 分析结果
   - JSON 格式，便于后续处理

### 项目结构

```
litellm_error_analyzer/
├── config.py                    # 配置文件（数据库、查询、LLM 配置）
├── query_error_logs_docker.py   # Docker 方式查询数据库
├── jupyter_error_analyzer.py    # 核心分析逻辑（可在 Jupyter 中使用）
├── run_analyzer.py              # 主运行脚本（命令行工具）
├── requirements.txt             # Python 依赖包
└── README.md                    # 本文件
```

---

## 🔧 代码实现原理

### 1. 数据库查询层 (`query_error_logs_docker.py`)

**实现方式：通过 Docker exec 执行 PostgreSQL 命令**

```python
# 核心实现：使用 subprocess 调用 docker exec
psql_cmd = [
    "docker", "exec",
    "-e", f"PGPASSWORD={password}",
    container_name,
    "psql",
    "-U", user,
    "-d", database,
    "-t", "-A",  # 只输出数据，非对齐格式
    "-c", sql_query
]
```

**为什么使用 Docker exec？**
- 无需暴露数据库端口到宿主机
- 更安全，避免网络访问
- 直接使用容器内的 PostgreSQL 客户端

**查询两个表：**
1. **LiteLLM_ErrorLogs** - 专门存储错误日志
2. **LiteLLM_SpendLogs** - 存储所有请求（筛选 status != 'success'）

**数据合并与去重：**
- 基于 `request_id` 去重
- 按时间倒序排序
- 支持限制返回条数

### 2. 查询逻辑层 (`jupyter_error_analyzer.py`)

**核心函数：**

#### `query_errors()` - 查询错误日志
```python
def query_errors(
    start_time,      # 开始时间
    end_time,        # 结束时间
    key_name,        # Key Alias 筛选
    model,           # 模型筛选
    limit,           # 限制条数
    db_config        # 数据库配置
)
```

**时间处理逻辑：**
- 如果 `use_time_filter=True` 且未指定时间，使用 `days_back` 计算最近 N 天
- 如果 `use_time_filter=False`，不进行时间筛选

#### `prepare_for_llm()` - 数据预处理
提取关键信息，减少发送给 LLM 的数据量：
- `request_id` - 请求 ID
- `time` - 时间戳
- `model` - 模型名称
- `key_name` - Key 别名
- `status` - 状态
- `error_type` - 错误类型
- `error_message` - 错误消息

#### `call_llm_api()` - 调用大模型
**支持的 API 格式：**
1. **OpenAI 兼容格式**（推荐）
   ```
   POST /v1/chat/completions
   {
     "model": "gpt-4",
     "messages": [...],
     "temperature": 0.3
   }
   ```

2. **Ollama 原生格式**
   ```
   POST /api/chat
   {
     "model": "llama2",
     "messages": [...],
     "stream": false
   }
   ```

**提示词设计：**
- 要求分析错误类型统计
- 识别主要问题
- 按模型分组分析
- 提供改进建议

### 3. 主运行脚本 (`run_analyzer.py`)

**执行流程：**

```
1. 加载配置 (config.py)
   ↓
2. 解析查询参数
   - 时间范围处理
   - 筛选条件验证
   ↓
3. 查询错误日志
   - 调用 query_errors()
   - 获取原始日志
   ↓
4. 准备分析数据
   - 调用 prepare_for_llm()
   - 提取关键信息
   ↓
5. 调用大模型分析（可选）
   - 如果 LLM_CONFIG['enabled'] = True
   - 调用 call_llm_api()
   ↓
6. 保存结果
   - 创建日期目录 (YYYY-MM-DD)
   - 保存完整日志、分析日志、LLM 结果
   ↓
7. 打印统计摘要
   - 按模型统计
   - 按错误类型统计
```

**输出文件：**
- `error_logs_full_{timestamp}.json` - 完整错误日志
- `error_logs_analysis_{timestamp}.json` - 简化后的分析日志
- `llm_analysis_{timestamp}.txt` - LLM 分析结果
- `query_params_{timestamp}.json` - 查询参数记录

---

## 🚀 环境准备

### 1. 安装 Python 依赖

```bash
cd litellm_error_analyzer
pip install -r requirements.txt
```

**依赖包说明：**
- `psycopg2-binary` - PostgreSQL 数据库驱动（虽然通过 Docker exec，但保留用于未来扩展）
- `requests` - HTTP 请求库（用于调用 LLM API）

### 2. 确认 Docker 环境

确保 Docker 容器正在运行：
```bash
docker ps | grep litellm-db-bak
```

如果容器未运行，需要先启动：
```bash
docker start litellm-db-bak
```

### 3. 验证数据库连接

```bash
docker exec -e PGPASSWORD=zhipu2025ddh litellm-db-bak psql -U litellm_user -d litellm_db -c "SELECT COUNT(*) FROM \"LiteLLM_ErrorLogs\";"
```

---

## ⚙️ 配置说明

### 配置文件：`config.py`

#### 1. 数据库配置 (`POSTGRES_CONFIG`)

```python
POSTGRES_CONFIG = {
    'container_name': 'litellm-db-bak',  # Docker 容器名称
    'database': 'litellm_db',            # 数据库名称
    'user': 'litellm_user',              # 用户名
    'password': 'zhipu2025ddh'           # 密码
}
```

**如何查找容器名称？**
```bash
docker ps
# 找到运行 PostgreSQL 的容器，复制 CONTAINER ID 或 NAMES
```

#### 2. 查询配置 (`QUERY_CONFIG`)

```python
QUERY_CONFIG = {
    'start_time': None,         # 开始时间，格式: "2025-12-01 00:00:00"
    'end_time': None,           # 结束时间，格式: "2025-12-23 23:59:59"
    'key_name': None,           # Key Alias 筛选，例如: "agent"（⚠️ 必须用引号！）
    'model': None,              # Model 筛选，例如: "external-qwen3-30b"
    'limit': 100,               # 限制返回条数
    'use_time_filter': True,    # 是否使用时间范围筛选
    'days_back': 1              # 默认查询最近1天（仅在 use_time_filter=True 时生效）
}
```

**配置示例：**

**示例 1：查询最近 1 天，特定 Key 的错误**
```python
QUERY_CONFIG = {
    'start_time': None,
    'end_time': None,
    'days_back': 1,
    'key_name': 'agent',  # ⚠️ 注意：必须用引号包裹！
    'limit': 50
}
```

**示例 2：查询指定时间范围，特定模型**
```python
QUERY_CONFIG = {
    'start_time': '2025-12-01 00:00:00',
    'end_time': '2025-12-23 23:59:59',
    'model': 'external-qwen3-30b',
    'limit': 100
}
```

**示例 3：只查询特定 Key，不使用时间筛选**
```python
QUERY_CONFIG = {
    'start_time': None,
    'end_time': None,
    'key_name': 'agent',
    'use_time_filter': False,  # 关闭时间筛选
    'limit': 100
}
```

#### 3. 大模型配置 (`LLM_CONFIG`)

```python
LLM_CONFIG = {
    'enabled': True,            # 是否启用大模型分析
    'api_url': 'http://10.163.25.156:5024/v1/chat/completions',  # LiteLLM Proxy API
    'api_key': 'zhipu2025ddh',  # LITELLM_MASTER_KEY
    'model': 'external-qwen3-30b',  # 模型名称（对应 config.yaml 中的 model_name）
    'timeout': 300              # 请求超时时间（秒）
}
```

**如何配置 LiteLLM Proxy？**
1. 查看 `docker-compose.yml` 中的 `LITELLM_MASTER_KEY`
2. 查看 `config.yaml` 中的模型配置，找到 `model_name`
3. 使用 LiteLLM Proxy 的地址（通常是 `http://<ip>:<port>/v1/chat/completions`）

**如果不想使用 LLM 分析：**
```python
LLM_CONFIG = {
    'enabled': False,  # 设置为 False 即可跳过 LLM 分析
    ...
}
```

#### 4. 输出配置 (`OUTPUT_CONFIG`)

```python
OUTPUT_CONFIG = {
    'output_dir': './output',     # 输出目录（相对路径）
    'save_full_logs': True,       # 是否保存完整错误日志
    'save_analysis_logs': True,   # 是否保存简化后的分析日志
    'save_llm_prompt': True,      # 是否保存 LLM 分析提示
    'save_llm_result': True        # 是否保存 LLM 分析结果
}
```

---

## 📝 使用方法

### 方法一：使用命令行工具（推荐）

1. **编辑配置文件**
   ```bash
   # 使用文本编辑器打开 config.py
   # 根据实际情况修改配置
   ```

2. **运行分析工具**
   ```bash
   python run_analyzer.py
   ```

3. **查看结果**
   ```bash
   # 结果保存在 output/YYYY-MM-DD/ 目录下
   ls output/2025-12-31/
   ```

**输出示例：**
```
============================================================
LiteLLM 错误日志分析工具
============================================================

[1/4] 加载配置...
✅ 配置加载成功

[2/4] 解析查询参数...
   使用默认时间范围: 最近 1 天
   Key Alias/Name: agent
   限制条数: 100

[3/4] 查询错误日志...
✅ 找到 45 条错误日志

[4/4] 调用大模型分析...
   正在分析 45 条日志，可能需要较长时间，请耐心等待...
✅ 大模型分析完成

[5/5] 保存结果...
📁 输出目录: C:\Users\10279\Desktop\litellm\litellm_error_analyzer\output\2025-12-31
✅ 完整错误日志已保存: error_logs_full_101433.json
✅ 分析日志已保存: error_logs_analysis_101433.json
✅ LLM 分析结果已保存: llm_analysis_101433.txt
✅ 查询参数已保存: query_params_101433.json

============================================================
统计摘要
============================================================
总错误数: 45

按模型统计:
  external-qwen3-30b: 30
  tiny-chat: 15

按错误类型统计:
  RateLimitError: 25
  APIError: 20

============================================================
✅ 分析完成
============================================================
```

### 方法二：在 Jupyter Notebook 中使用

1. **导入模块**
   ```python
   from jupyter_error_analyzer import analyze_errors
   ```

2. **基本查询（不使用 LLM）**
   ```python
   result = analyze_errors(
       start_time="2025-12-01 00:00:00",
       end_time="2025-12-23 23:59:59",
       limit=50
   )
   
   # 查看结果
   print(f"找到 {len(result['error_logs'])} 条错误日志")
   print(result['summary'])
   ```

3. **带筛选条件的查询**
   ```python
   result = analyze_errors(
       start_time="2025-12-01 00:00:00",
       end_time="2025-12-23 23:59:59",
       model="external-qwen3-30b",  # 筛选特定模型
       key_name="agent",            # 筛选特定 key
       limit=100
   )
   ```

4. **查询并调用大模型分析**
   ```python
   result = analyze_errors(
       start_time="2025-12-22 00:00:00",
       end_time="2025-12-23 23:59:59",
       model="external-qwen3-30b",
       limit=50,
       llm_api_url="http://10.163.25.156:5024/v1/chat/completions",
       llm_api_key="zhipu2025ddh",
       llm_model="external-qwen3-30b"
   )
   
   # 查看 LLM 分析结果
   if result['llm_analysis']:
       print(result['llm_analysis'])
   ```

### 方法三：直接使用查询函数

```python
from jupyter_error_analyzer import query_errors, prepare_for_llm

# 查询错误日志
error_logs = query_errors(
    start_time="2025-12-01 00:00:00",
    end_time="2025-12-23 23:59:59",
    key_name="agent",
    model="external-qwen3-30b",
    limit=100
)

# 准备分析数据
analysis_logs = prepare_for_llm(error_logs)

# 查看第一条日志
import json
print(json.dumps(analysis_logs[0], indent=2, ensure_ascii=False))
```

---

## 🏗️ 代码架构详解

### 数据流图

```
┌─────────────────┐
│   config.py     │  ← 配置文件（数据库、查询、LLM 配置）
└────────┬────────┘
         │
         ↓
┌─────────────────────────┐
│   run_analyzer.py       │  ← 主运行脚本
│   - load_config()       │
│   - parse_time()         │
│   - main()               │
└────────┬────────────────┘
         │
         ↓
┌─────────────────────────┐
│ jupyter_error_analyzer  │  ← 核心分析逻辑
│   - query_errors()       │  ← 查询错误日志
│   - prepare_for_llm()    │  ← 数据预处理
│   - call_llm_api()       │  ← 调用大模型
└────────┬────────────────┘
         │
         ↓
┌─────────────────────────┐
│query_error_logs_docker  │  ← 数据库查询层
│   - LiteLLMErrorLogQuery│
│   - _execute_sql_json() │  ← Docker exec 执行 SQL
│   - query_error_logs()  │  ← 查询两个表并合并
└────────┬────────────────┘
         │
         ↓
┌─────────────────────────┐
│   Docker Container      │
│   PostgreSQL Database   │
│   - LiteLLM_ErrorLogs   │
│   - LiteLLM_SpendLogs   │
└─────────────────────────┘
```

### 关键函数说明

#### `LiteLLMErrorLogQueryDocker._execute_sql_json()`

**功能：** 通过 Docker exec 执行 SQL 并返回 JSON

**实现原理：**
1. 构建 `docker exec` 命令
2. 使用 PostgreSQL 的 `json_agg()` 函数将结果聚合为 JSON
3. 通过 `subprocess.run()` 执行命令
4. 解析返回的 JSON 字符串

**SQL 转换：**
```sql
-- 原始 SQL
SELECT * FROM "LiteLLM_ErrorLogs" WHERE ...

-- 转换为 JSON
SELECT json_agg(row_to_json(t)) FROM (
    SELECT * FROM "LiteLLM_ErrorLogs" WHERE ...
) t;
```

#### `LiteLLMErrorLogQueryDocker.query_error_logs()`

**功能：** 查询错误日志（支持三个筛选条件）

**查询策略：**
1. 同时查询 `ErrorLogs` 和 `SpendLogs` 两个表
2. 基于 `request_id` 去重
3. 按时间倒序排序
4. 限制返回条数

**为什么查询两个表？**
- `ErrorLogs` 表：专门存储错误，但可能不包含所有错误
- `SpendLogs` 表：包含所有请求，通过 `status != 'success'` 筛选错误

#### `prepare_for_llm()`

**功能：** 提取关键信息，减少发送给 LLM 的数据量

**提取字段：**
- `request_id` - 用于追踪
- `time` - 时间信息
- `model` - 模型名称
- `key_name` - Key 别名
- `status` - 状态码
- `error_type` - 错误类型（从 `exception_type` 或 `metadata.error_information.error_class` 提取）
- `error_message` - 错误消息（从 `exception_string` 或 `metadata.error_information.error_message` 提取）

**为什么需要预处理？**
- 原始日志包含大量冗余信息
- 减少 API 调用成本
- 提高分析效率

#### `call_llm_api()`

**功能：** 调用大模型 API 分析错误日志

**支持的 API 格式：**
1. **OpenAI 兼容格式**（标准）
2. **Ollama 原生格式**（自动检测 `/api/chat` 路径）

**错误处理：**
- JSON 解析失败时尝试多行解析
- 超时设置（默认 600 秒）
- 详细的错误信息返回

---

## ❓ 常见问题

### 1. Docker 容器连接失败

**错误信息：**
```
❌ SQL 执行失败: CalledProcessError
```

**解决方法：**
```bash
# 1. 检查容器是否运行
docker ps | grep litellm-db-bak

# 2. 如果未运行，启动容器
docker start litellm-db-bak

# 3. 验证容器名称是否正确
docker ps
# 复制正确的容器名称到 config.py 的 container_name
```

### 2. 查询结果为空

**可能原因：**
1. 时间范围设置错误
2. 筛选条件太严格
3. 数据库中确实没有错误日志

**排查步骤：**
```python
# 1. 先不使用时间筛选
QUERY_CONFIG = {
    'use_time_filter': False,
    'limit': 10
}

# 2. 逐步添加筛选条件
# 3. 检查数据库是否有数据
docker exec -e PGPASSWORD=zhipu2025ddh litellm-db-bak \
  psql -U litellm_user -d litellm_db \
  -c "SELECT COUNT(*) FROM \"LiteLLM_ErrorLogs\";"
```

### 3. LLM API 调用失败

**错误信息：**
```
⚠️ 调用大模型失败: Connection timeout
```

**解决方法：**
1. **检查 API URL 是否正确**
   ```python
   # 测试 API 是否可访问
   import requests
   response = requests.get('http://10.163.25.156:5024/health', timeout=5)
   ```

2. **增加超时时间**
   ```python
   LLM_CONFIG = {
       'timeout': 600  # 增加到 10 分钟
   }
   ```

3. **检查 API Key**
   ```python
   # 确认 LITELLM_MASTER_KEY 是否正确
   # 查看 docker-compose.yml
   ```

4. **如果不需要 LLM 分析，可以关闭**
   ```python
   LLM_CONFIG = {
       'enabled': False
   }
   ```

### 4. Key Alias 筛选不生效

**原因：** Key Alias 存储在 `metadata->user_api_key_alias` JSON 字段中

**解决方法：**
```python
# 确保使用正确的 Key Alias 名称
# 可以通过查询数据库确认
docker exec -e PGPASSWORD=zhipu2025ddh litellm-db-bak \
  psql -U litellm_user -d litellm_db \
  -c "SELECT DISTINCT metadata->>'user_api_key_alias' FROM \"LiteLLM_SpendLogs\" LIMIT 10;"
```

### 5. 中文乱码问题（Windows）

**问题：** 控制台输出中文乱码

**解决：** 代码已自动处理（`run_analyzer.py` 第 13-16 行）
```python
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
```

如果仍有问题，设置 PowerShell 编码：
```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
```

### 6. 输出目录权限问题

**错误信息：**
```
⚠️ 无法创建输出目录
```

**解决方法：**
```python
# 修改输出目录为有写权限的位置
OUTPUT_CONFIG = {
    'output_dir': 'C:/Users/YourName/Desktop/output',  # 使用绝对路径
    ...
}
```

---

## 📚 扩展开发

### 添加新的筛选条件

1. **修改 `query_error_logs_docker.py`**
   ```python
   def query_error_logs(self, ..., new_filter=None):
       if new_filter:
           conditions.append(f'"field" = \'{new_filter}\'')
   ```

2. **修改 `jupyter_error_analyzer.py`**
   ```python
   def query_errors(..., new_filter=None):
       # 传递新参数
   ```

3. **修改 `config.py`**
   ```python
   QUERY_CONFIG = {
       'new_filter': None,
       ...
   }
   ```

### 支持其他数据库

可以修改 `query_error_logs_docker.py`，添加直接连接数据库的方式：

```python
import psycopg2

def _execute_sql_direct(self, sql: str):
    conn = psycopg2.connect(
        host=self.host,
        port=self.port,
        database=self.database,
        user=self.user,
        password=self.password
    )
    # ...
```

---

## 📞 技术支持

如有问题，请检查：
1. Docker 容器是否正常运行
2. 配置文件是否正确
3. 数据库连接是否正常
4. LLM API 是否可访问

---

## 📖 操作文档

### 📋 工具介绍

这是一个用于查询和分析 LiteLLM 错误日志的 Python 工具。它可以从 LiteLLM 的 PostgreSQL 数据库中查询错误日志，并支持使用大语言模型（LLM）对错误进行智能分析。

#### 主要功能

1. **错误日志查询**：支持三个筛选条件
   - 时间范围筛选
   - 模型名称筛选
   - API Key Alias 筛选

2. **智能分析**：可选的大语言模型分析
   - 错误类型统计
   - 问题根因分析
   - 改进建议

3. **结果保存**：自动保存查询结果和分析报告
   - 完整错误日志（JSON 格式）
   - 简化分析日志（JSON 格式）
   - LLM 分析报告（文本格式）

---

### 🚀 快速开始

#### 1. 环境要求

- Python 3.11 或更高版本
- Docker（用于访问 LiteLLM 数据库）
- 已安装的依赖包（见 `requirements.txt`）

#### 2. 安装依赖

```bash
pip install -r requirements.txt
```

依赖包：
- `psycopg2-binary>=2.9.0` - PostgreSQL 数据库连接
- `requests>=2.28.0` - HTTP 请求（用于 LLM API 调用）

#### 3. 配置文件

编辑 `config.py` 文件，配置以下内容：

##### 3.1 数据库配置

```python
POSTGRES_CONFIG = {
    'container_name': 'litellm-db-bak',  # Docker 容器名称
    'database': 'litellm_db',            # 数据库名称
    'user': 'litellm_user',              # 用户名
    'password': 'zhipu2025ddh'           # 密码
}
```

**说明**：
- 工具通过 `docker exec` 方式访问数据库，无需端口映射
- 确保 Docker 容器正在运行：`docker ps | grep litellm-db-bak`

##### 3.2 查询配置

```python
QUERY_CONFIG = {
    'start_time': None,         # 开始时间，例如: "2025-12-01 00:00:00"
    'end_time': None,           # 结束时间，例如: "2025-12-23 23:59:59"
    'key_name': None,           # Key Alias 筛选，例如: "agent"（注意：必须用引号包裹！）
    'model': None,              # Model 筛选，例如: "external-qwen3-30b"
    'limit': 100,               # 限制返回条数
    'use_time_filter': True,    # 是否使用时间范围筛选
    'days_back': 1              # 默认查询最近1天（仅在 use_time_filter=True 时生效）
}
```

**配置说明**：
- **时间范围**：如果 `start_time` 和 `end_time` 都为 `None`，且 `use_time_filter=True`，则使用 `days_back` 查询最近 N 天
- **Key Alias**：必须用引号包裹，例如 `'agent'` 而不是 `agent`
- **关闭时间筛选**：设置 `use_time_filter=False` 可以只按模型或 Key Alias 筛选

##### 3.3 LLM 配置

```python
LLM_CONFIG = {
    'enabled': True,            # 是否启用大模型分析
    'api_url': 'http://10.163.25.156:5024/v1/chat/completions',  # LiteLLM Proxy API
    'api_key': 'zhipu2025ddh',  # LITELLM_MASTER_KEY
    'model': 'external-qwen3-30b',  # 模型名称
    'timeout': 300              # 请求超时时间（秒）
}
```

**说明**：
- 支持 LiteLLM Proxy（OpenAI 兼容格式）
- 如果不需要 LLM 分析，设置 `enabled: False`

##### 3.4 输出配置

```python
OUTPUT_CONFIG = {
    'output_dir': './output',     # 输出目录
    'save_full_logs': True,       # 是否保存完整错误日志
    'save_analysis_logs': True,   # 是否保存简化后的分析日志
    'save_llm_result': True       # 是否保存 LLM 分析结果
}
```

---

### 📖 使用方法

#### 基本使用

```bash
python run_analyzer.py
```

#### 使用示例

##### 示例 1：查询最近 1 天的错误日志

```python
# config.py
QUERY_CONFIG = {
    'start_time': None,
    'end_time': None,
    'key_name': None,
    'model': None,
    'limit': 100,
    'use_time_filter': True,
    'days_back': 1
}
```

##### 示例 2：查询特定时间范围、模型和 Key Alias

```python
# config.py
QUERY_CONFIG = {
    'start_time': '2025-12-01 00:00:00',
    'end_time': '2025-12-23 23:59:59',
    'key_name': 'agent',  # ⚠️ 注意：必须用引号包裹！
    'model': 'external-qwen3-30b',
    'limit': 100,
    'use_time_filter': True,
    'days_back': 1
}
```

##### 示例 3：只筛选模型，不使用时间范围

```python
# config.py
QUERY_CONFIG = {
    'start_time': None,
    'end_time': None,
    'key_name': None,
    'model': 'external-qwen3-30b',
    'limit': 100,
    'use_time_filter': False,  # 关闭时间筛选
    'days_back': 1
}
```

##### 示例 4：只筛选 Key Alias，不使用时间范围

```python
# config.py
QUERY_CONFIG = {
    'start_time': None,
    'end_time': None,
    'key_name': 'agent',  # ⚠️ 注意：必须用引号包裹！
    'model': None,
    'limit': 100,
    'use_time_filter': False,  # 关闭时间筛选
    'days_back': 1
}
```

---

### 📁 输出文件说明

运行后，结果会保存在 `output/YYYY-MM-DD/` 目录下（按日期创建子目录）。

#### 输出文件类型

1. **error_logs_full_时间戳.json**
   - 完整的错误日志数据
   - 包含所有字段信息
   - 用于详细分析

2. **error_logs_analysis_时间戳.json**
   - 简化后的分析日志
   - 只包含关键字段：request_id、time、model、key_name、status、error_type、error_message
   - 用于快速查看

3. **llm_analysis_时间戳.txt**
   - LLM 分析报告（如果启用了 LLM 分析）
   - 包含错误统计、问题分析、改进建议

4. **query_params_时间戳.json**
   - 查询参数记录
   - 记录本次查询的配置和结果统计

#### 输出目录结构

```
output/
└── 2025-12-25/
    ├── error_logs_full_101530.json
    ├── error_logs_analysis_101530.json
    ├── llm_analysis_101530.txt
    └── query_params_101530.json
```

---

### 🔍 筛选条件详解

#### 1. 时间范围筛选

**使用场景**：查询特定时间段的错误日志

**配置方式**：
```python
'start_time': '2025-12-01 00:00:00',
'end_time': '2025-12-23 23:59:59',
'use_time_filter': True
```

**或者使用相对时间**：
```python
'start_time': None,
'end_time': None,
'use_time_filter': True,
'days_back': 7  # 查询最近 7 天
```

#### 2. 模型名称筛选

**使用场景**：只查询特定模型的错误日志

**配置方式**：
```python
'model': 'external-qwen3-30b'
```

**说明**：
- 模型名称必须与 LiteLLM 中配置的模型名称完全匹配
- 可以在 LiteLLM 的 `config.yaml` 中查看模型名称

#### 3. Key Alias 筛选

**使用场景**：只查询特定 API Key 的错误日志

**配置方式**：
```python
'key_name': 'agent'  # ⚠️ 注意：必须用引号包裹！
```

**重要提示**：
- **必须用引号包裹**，否则会报错 `name 'xxx' is not defined`
- Key Alias 是 LiteLLM 中配置的 API Key 别名
- 可以在 LiteLLM 管理界面查看 Key Alias

#### 4. 组合筛选

可以同时使用多个筛选条件：

```python
QUERY_CONFIG = {
    'start_time': '2025-12-01 00:00:00',
    'end_time': '2025-12-23 23:59:59',
    'key_name': 'agent',
    'model': 'external-qwen3-30b',
    'limit': 100,
    'use_time_filter': True
}
```

---

### 🛠️ 技术说明

#### 数据库查询方式

工具使用 `docker exec` 方式访问 PostgreSQL 数据库，无需端口映射：

```python
docker exec -e PGPASSWORD=密码 容器名 psql -U 用户名 -d 数据库名
```

**优势**：
- 无需暴露数据库端口
- 更安全
- 适用于容器化部署

#### 数据表说明

##### LiteLLM_SpendLogs 表（主要使用）

- **时间字段**：`startTime`
- **模型字段**：`model`
- **Key 字段**：`metadata->>'user_api_key_alias'`（存储在 JSON 中）
- **状态字段**：`status`（'success' 表示成功，其他为错误）

**SQL 查询示例**：
```sql
SELECT * FROM "LiteLLM_SpendLogs" 
WHERE 
    "startTime" >= '2025-12-01 00:00:00'::timestamp
    AND "model" = 'external-qwen3-30b'
    AND metadata->>'user_api_key_alias' = 'agent'
    AND "status" != 'success'
```

##### LiteLLM_ErrorLogs 表（辅助使用）

- **时间字段**：`startTime`
- **模型字段**：`litellm_model_name`
- **⚠️ 注意**：此表没有 Key 相关字段，无法通过 Key Alias 筛选

#### 工作流程

1. **加载配置**：从 `config.py` 读取配置
2. **解析参数**：处理时间范围、模型、Key Alias 等筛选条件
3. **查询数据库**：通过 `docker exec` 执行 SQL 查询
4. **数据处理**：提取关键信息，准备分析数据
5. **LLM 分析**（可选）：调用大语言模型 API 进行分析
6. **保存结果**：将结果保存到 `output/日期/` 目录

---

### ❓ 常见问题

#### Q1: 报错 `name 'agent' is not defined`

**原因**：在 `config.py` 中设置 `key_name` 时没有用引号包裹

**解决方法**：
```python
# ❌ 错误
'key_name': agent

# ✅ 正确
'key_name': 'agent'
```

#### Q2: 报错 `No such container: litellm-db-bak`

**原因**：Docker 容器名称不正确或容器未运行

**解决方法**：
1. 检查容器名称：`docker ps`
2. 修改 `config.py` 中的 `container_name`
3. 确保容器正在运行

#### Q3: 查询不到数据

**可能原因**：
1. 时间范围设置错误
2. 模型名称不匹配
3. Key Alias 不存在
4. 该时间段内确实没有错误日志

**解决方法**：
1. 先不使用筛选条件，查询所有错误日志
2. 检查数据库中的实际数据
3. 确认模型名称和 Key Alias 是否正确

#### Q4: LLM 分析失败

**可能原因**：
1. LLM API 地址不正确
2. API Key 错误
3. 网络连接问题
4. 模型名称不匹配

**解决方法**：
1. 检查 `LLM_CONFIG` 中的配置
2. 测试 API 连接：`curl -X POST http://...`
3. 查看错误日志中的详细错误信息

#### Q5: 输出目录不存在

**解决方法**：
- 工具会自动创建输出目录
- 如果创建失败，检查文件系统权限

---

### 📊 使用场景示例

#### 场景 1：日常错误监控

**需求**：每天查看最近 1 天的错误日志

**配置**：
```python
QUERY_CONFIG = {
    'start_time': None,
    'end_time': None,
    'use_time_filter': True,
    'days_back': 1,
    'limit': 100
}
LLM_CONFIG = {
    'enabled': True  # 启用 LLM 分析
}
```

**执行**：
```bash
python run_analyzer.py
```

#### 场景 2：特定模型问题排查

**需求**：排查某个模型的错误问题

**配置**：
```python
QUERY_CONFIG = {
    'start_time': '2025-12-20 00:00:00',
    'end_time': '2025-12-25 23:59:59',
    'model': 'external-qwen3-30b',
    'use_time_filter': True,
    'limit': 200
}
```

#### 场景 3：特定 Key 的错误分析

**需求**：分析某个 API Key 的错误情况

**配置**：
```python
QUERY_CONFIG = {
    'start_time': None,
    'end_time': None,
    'key_name': 'agent',
    'use_time_filter': False,  # 不限制时间
    'limit': 100
}
```

#### 场景 4：问题根因分析

**需求**：深入分析错误原因，获取改进建议

**配置**：
```python
QUERY_CONFIG = {
    'start_time': '2025-12-20 00:00:00',
    'end_time': '2025-12-25 23:59:59',
    'limit': 50  # 限制数量，便于 LLM 分析
}
LLM_CONFIG = {
    'enabled': True,
    'timeout': 600  # 增加超时时间
}
```

---

### 🔧 高级配置

#### 自定义输出目录

```python
OUTPUT_CONFIG = {
    'output_dir': '/data/litellm/error_analysis',  # 绝对路径
    'save_full_logs': True,
    'save_analysis_logs': True,
    'save_llm_result': True
}
```

#### 调整查询限制

```python
QUERY_CONFIG = {
    'limit': 500  # 增加查询条数（注意：LLM 分析可能需要更长时间）
}
```

#### 禁用 LLM 分析（仅查询）

```python
LLM_CONFIG = {
    'enabled': False  # 只查询，不分析
}
```

---

### ⏰ 定时任务配置

#### Linux Cron 定时任务

如果需要每天自动运行错误日志分析，可以使用 Linux 的 `crontab` 定时任务。

##### 1. 编辑 crontab

```bash
crontab -e
```

##### 2. 添加定时任务

**每天 19:10 执行**：
```bash
10 19 * * * cd /path/to/litellm_error_analyzer && /usr/bin/python3 run_analyzer.py >> /var/log/litellm_analyzer.log 2>&1
```

**Cron 表达式格式**：
```
分 时 日 月 星期
```

**常用时间示例**：

| 说明 | Cron 表达式 | 示例 |
|------|------------|------|
| 每天 19:10 | `10 19 * * *` | 每天 19:10 执行 |
| 每天 00:00 | `0 0 * * *` | 每天午夜执行 |
| 每天 09:30 | `30 9 * * *` | 每天上午 9:30 执行 |
| 每小时 | `0 * * * *` | 每小时整点执行 |
| 每 30 分钟 | `*/30 * * * *` | 每 30 分钟执行一次 |
| 每周一 10:00 | `0 10 * * 1` | 每周一 10:00 执行 |
| 每月 1 号 08:00 | `0 8 1 * *` | 每月 1 号 8:00 执行 |

**字段说明**：
- **分**：0-59
- **时**：0-23
- **日**：1-31
- **月**：1-12 或 JAN-DEC
- **星期**：0-7（0 和 7 都表示周日）或 SUN-SAT

##### 3. 完整定时任务示例

```bash
# 每天 19:10 执行错误日志分析
10 19 * * * cd /home/user/litellm_error_analyzer && /usr/bin/python3 run_analyzer.py >> /var/log/litellm_analyzer.log 2>&1

# 每天 00:00 执行（查询前一天的错误）
0 0 * * * cd /home/user/litellm_error_analyzer && /usr/bin/python3 run_analyzer.py >> /var/log/litellm_analyzer.log 2>&1
```

**注意事项**：
1. 使用绝对路径：确保 `cd` 和 Python 路径都是绝对路径
2. 日志输出：`>>` 表示追加日志，`2>&1` 表示将错误输出也重定向到日志文件
3. 环境变量：如果 Python 脚本依赖特定环境变量，需要在 crontab 中设置：
   ```bash
   10 19 * * * export PATH=/usr/local/bin:$PATH && cd /path/to/litellm_error_analyzer && /usr/bin/python3 run_analyzer.py
   ```

##### 4. 查看定时任务

```bash
# 查看当前用户的定时任务
crontab -l

# 查看定时任务执行日志（Ubuntu/Debian）
grep CRON /var/log/syslog

# 查看定时任务执行日志（CentOS/RHEL）
grep CRON /var/log/cron
```

#### Windows 定时任务

##### 使用任务计划程序

1. 打开"任务计划程序"（Task Scheduler）
2. 创建基本任务
3. 设置触发器：每天 19:10
4. 设置操作：启动程序
   - 程序：`python.exe` 的完整路径
   - 参数：`run_analyzer.py`
   - 起始于：`C:\Users\10279\Desktop\litellm\litellm_error_analyzer`

##### 使用 PowerShell 创建定时任务

```powershell
$action = New-ScheduledTaskAction -Execute "python.exe" -Argument "run_analyzer.py" -WorkingDirectory "C:\Users\10279\Desktop\litellm\litellm_error_analyzer"
$trigger = New-ScheduledTaskTrigger -Daily -At "19:10"
Register-ScheduledTask -TaskName "LiteLLM错误日志分析" -Action $action -Trigger $trigger
```

---

### 📝 注意事项

1. **Key Alias 必须用引号包裹**：`'agent'` 而不是 `agent`
2. **时间格式**：使用 `"YYYY-MM-DD HH:MM:SS"` 格式
3. **容器名称**：确保 Docker 容器名称正确
4. **LLM 分析**：大量日志可能需要较长时间，建议设置合理的 `limit`
5. **输出目录**：工具会自动创建按日期命名的子目录

---

### 🆘 获取帮助

如果遇到问题：

1. 检查配置文件 `config.py` 是否正确
2. 查看错误日志中的详细错误信息
3. 确认 Docker 容器是否正常运行
4. 测试数据库连接：`docker exec -e PGPASSWORD=密码 容器名 psql -U 用户名 -d 数据库名`

---

**最后更新**: 2025-12-31
