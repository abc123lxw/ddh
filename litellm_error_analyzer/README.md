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

**最后更新**: 2025-12-31
