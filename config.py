"""
LiteLLM 错误日志分析工具配置文件
请根据实际情况修改以下配置
"""

# ==================== LiteLLM 数据库连接配置 ====================
# PostgreSQL 数据库连接配置（通过 Docker exec 方式，无需端口映射）
POSTGRES_CONFIG = {
    'container_name': 'litellm-db-bak',  # Docker 容器名称
    'database': 'litellm_db',            # 数据库名称
    'user': 'litellm_user',              # 用户名
    'password': 'zhipu2025ddh'           # 密码
}

# ==================== 查询筛选条件配置 ====================
# 时间范围（格式: "YYYY-MM-DD HH:MM:SS" 或 None 表示不限制）
QUERY_CONFIG = {
    'start_time': None,         # 开始时间，例如: "2025-12-01 00:00:00"
    'end_time': None,           # 结束时间，例如: "2025-12-23 23:59:59"
    'key_name': None,           # Key Alias 筛选（可选），例如: "agent"（注意：必须用引号包裹！）
    'model': None,              # Model 筛选（可选），例如: "external-qwen3-30b"
    'limit': 100,               # 限制返回条数
    'use_time_filter': True,    # 是否使用时间范围筛选（True/False）
    # 如果 use_time_filter=True 且 start_time 和 end_time 都为 None，则使用 days_back
    'days_back': 1              # 默认查询最近1天（仅在 use_time_filter=True 时生效）
}

# ==================== 大模型分析配置 ====================
# 使用 LiteLLM Proxy 进行错误日志分析
# LiteLLM Proxy 支持 OpenAI 兼容格式，可以使用配置的模型
LLM_CONFIG = {
    'enabled': True,            # 是否启用大模型分析（True/False）
    'api_url': 'http://10.163.25.156:5024/v1/chat/completions',  # LiteLLM Proxy OpenAI 兼容 API
    'api_key': 'zhipu2025ddh',  # LITELLM_MASTER_KEY（从 docker-compose.yml 获取）
    'model': 'external-qwen3-30b',  # 使用你配置的模型名称（对应 config.yaml 中的 model_name）
    'timeout': 300              # 请求超时时间（秒）
}

# ==================== 输出配置 ====================
OUTPUT_CONFIG = {
    'output_dir': './output',     # 输出目录（相对路径，Windows 和 Linux 都支持）
    'save_full_logs': True,       # 是否保存完整错误日志
    'save_analysis_logs': True,   # 是否保存简化后的分析日志
    'save_llm_prompt': True,      # 是否保存 LLM 分析提示（即使不调用 API）
    'save_llm_result': True        # 是否保存 LLM 分析结果
}

# ==================== 示例配置 ====================
# 如果需要使用示例配置，取消下面的注释并修改

# 示例1: 查询最近1天，特定 Key Alias 的错误
# QUERY_CONFIG = {
#     'start_time': None,
#     'end_time': None,
#     'days_back': 1,
#     'key_name': 'agent',  # ⚠️ 注意：必须用引号包裹！'agent' 而不是 agent
#     'limit': 50
# }

# 示例2: 查询指定时间范围，特定 Key Alias 和模型
# QUERY_CONFIG = {
#     'start_time': '2025-12-01 00:00:00',
#     'end_time': '2025-12-23 23:59:59',
#     'key_name': 'agent',  # ⚠️ 注意：必须用引号包裹！
#     'model': 'external-qwen3-30b',
#     'limit': 100
# }

# 示例3: 只查询特定 Key Alias，不使用时间筛选
# QUERY_CONFIG = {
#     'start_time': None,
#     'end_time': None,
#     'key_name': 'agent',  # ⚠️ 注意：必须用引号包裹！
#     'use_time_filter': False,  # 关闭时间筛选
#     'limit': 100
# }

# 示例4: 从容器内连接数据库（使用容器名）
# POSTGRES_CONFIG = {
#     'host': 'db',  # 使用容器名
#     'port': 5432,
#     'database': 'litellm_db',
#     'user': 'litellm_user',
#     'password': 'zhipu2025ddh'
# }
