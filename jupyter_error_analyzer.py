"""
LiteLLM 错误日志查询与分析脚本（Jupyter 版本）
支持三个筛选条件：时间范围、Key Name、Model
查询错误日志并调用大模型分析

使用方法（在 Jupyter 中）:
    from jupyter_error_analyzer import analyze_errors
    
    # 查询并分析错误日志
    result = analyze_errors(
        start_time="2025-12-01 00:00:00",
        end_time="2025-12-23 23:59:59",
        key_name=None,  # 可选
        model="tiny-chat",  # 可选
        limit=100
    )
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import json


def query_errors(
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    key_name: Optional[str] = None,
    model: Optional[str] = None,
    limit: Optional[int] = 100,
    db_config: Optional[Dict] = None
) -> List[Dict[str, Any]]:
    """
    查询错误日志（三个筛选条件）
    
    Args:
        start_time: 开始时间，格式 "YYYY-MM-DD HH:MM:SS" 或 datetime 对象
        end_time: 结束时间，格式 "YYYY-MM-DD HH:MM:SS" 或 datetime 对象
        key_name: Key Name 筛选（可选）
        model: Model 筛选（可选）
        limit: 限制返回条数（默认100）
        db_config: 数据库配置（可选，默认从 config.py 读取）
    
    Returns:
        错误日志列表，每个元素是一个字典，包含单条日志的所有信息
    """
    # 解析时间字符串
    if isinstance(start_time, str):
        start_time = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
    if isinstance(end_time, str):
        end_time = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
    
    # 检查是否需要使用时间筛选
    # 如果 db_config 中有 use_time_filter 配置，使用它；否则默认使用时间筛选
    use_time_filter = db_config.get('use_time_filter', True) if db_config else True
    
    # 如果没有指定时间范围，根据 use_time_filter 决定
    if use_time_filter:
        if start_time is None and end_time is None:
            # 使用 days_back（如果配置了）
            days_back = db_config.get('days_back', 7) if db_config else 7
            if days_back is not None:
                end_time = datetime.now()
                start_time = end_time - timedelta(days=days_back)
    else:
        # 不使用时间筛选，设置为 None
        start_time = None
        end_time = None
    
    # 获取数据库配置
    if db_config is None:
        try:
            from config import POSTGRES_CONFIG
            db_config = POSTGRES_CONFIG
        except ImportError:
            db_config = {
                'container_name': 'litellm-db-bak',
                'database': 'litellm_db',
                'user': 'litellm_user',
                'password': 'zhipu2025ddh'
            }
    
    # 使用 Docker exec 方式（推荐，无需端口映射）
    from query_error_logs_docker import LiteLLMErrorLogQueryDocker
    query = LiteLLMErrorLogQueryDocker(
        container_name=db_config.get('container_name', 'litellm-db-bak'),
        database=db_config['database'],
        user=db_config['user'],
        password=db_config['password']
    )
    
    # 查询错误日志
    error_logs = query.query_error_logs(
        start_time=start_time,
        end_time=end_time,
        key_name=key_name,
        model=model,
        limit=limit
    )
    
    return error_logs


def prepare_for_llm(error_logs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    准备日志数据用于大模型分析（提取关键信息）
    
    Args:
        error_logs: 原始错误日志列表
    
    Returns:
        简化后的日志列表，包含关键信息
    """
    analysis_logs = []
    
    for log in error_logs:
        # 提取关键信息
        item = {
            'request_id': log.get('request_id', ''),
            'time': str(log.get('startTime', '')),
            'model': log.get('model', ''),
            'key_name': log.get('key_name') or log.get('api_key', ''),
            'status': log.get('status', ''),
            'error_type': log.get('exception_type', ''),
            'error_message': log.get('exception_string', ''),
        }
        
        # 从 metadata 中提取错误信息
        metadata = log.get('metadata', {})
        if isinstance(metadata, dict):
            error_info = metadata.get('error_information', {})
            if error_info:
                if not item['error_type']:
                    item['error_type'] = error_info.get('error_class', '')
                if not item['error_message']:
                    item['error_message'] = error_info.get('error_message', '')
        
        analysis_logs.append(item)
    
    return analysis_logs


def call_llm_api(
    error_logs: List[Dict[str, Any]],
    api_url: str,
    api_key: Optional[str] = None,
    model: str = "gpt-4"
) -> str:
    """
    调用大模型 API 分析错误日志
    支持 OpenAI 兼容格式和 Ollama 原生格式
    
    Args:
        error_logs: 错误日志列表（简化后的）
        api_url: LLM API 地址
            - OpenAI 格式: "https://api.openai.com/v1/chat/completions"
            - Ollama OpenAI 兼容: "http://localhost:11434/v1/chat/completions"
            - Ollama 原生: "http://localhost:11434/api/chat"
        api_key: API Key（如果需要）
        model: 模型名称（默认: gpt-4）
    
    Returns:
        分析结果文本
    """
    try:
        import requests
        
        # 准备日志数据
        logs_json = json.dumps(error_logs, ensure_ascii=False, indent=2, default=str)
        
        # 构建提示
        prompt = f"""请分析以下 LiteLLM 错误日志，并提供详细的分析报告：

1. **错误类型统计**：列出所有错误类型及其出现次数
2. **主要问题**：识别最常见的错误原因，并分析根本原因
3. **模型相关错误**：按模型分组统计错误，分析哪些模型问题最多
4. **时间分布**：分析错误的时间分布模式（是否有集中爆发）
5. **改进建议**：针对每种错误类型提供具体的改进建议

错误日志数据：
{logs_json}

请以结构化的方式提供分析结果，包括统计数据和具体建议。"""
        
        # 判断是否为 Ollama 原生 API
        is_ollama_native = '/api/chat' in api_url
        
        # 准备请求头
        headers = {
            "Content-Type": "application/json"
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        
        # 准备请求体
        if is_ollama_native:
            # Ollama 原生 API 格式
            payload = {
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": "你是一个专业的错误日志分析专家，擅长分析 API 调用错误、系统故障和性能问题。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "stream": False,
                "options": {
                    "temperature": 0.3
                }
            }
        else:
            # OpenAI 兼容格式
            payload = {
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": "你是一个专业的错误日志分析专家，擅长分析 API 调用错误、系统故障和性能问题。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.3
            }
        
        # 发送请求
        # 从配置中获取超时时间，默认 300 秒
        timeout = 600  # 增加超时时间到 10 分钟，因为分析大量日志可能需要更长时间
        response = requests.post(api_url, json=payload, headers=headers, timeout=timeout)
        
        if response.status_code == 200:
            try:
                result = response.json()
            except json.JSONDecodeError as e:
                # 尝试处理可能的流式响应或格式问题
                text = response.text.strip()
                # 如果是多行 JSON，尝试解析第一行
                if '\n' in text:
                    lines = text.split('\n')
                    for line in lines:
                        if line.strip():
                            try:
                                result = json.loads(line)
                                break
                            except:
                                continue
                    else:
                        return f"无法解析 JSON 响应: {text[:500]}"
                else:
                    return f"JSON 解析失败: {str(e)}, 响应内容: {text[:500]}"
            
            # 处理 Ollama 原生 API 响应
            if is_ollama_native:
                if 'message' in result and 'content' in result['message']:
                    return result['message']['content']
                elif 'response' in result:
                    # 某些 Ollama 版本可能直接返回 response
                    return result['response']
                else:
                    return f"Ollama API 返回格式异常: {result}"
            
            # 处理 OpenAI 兼容格式响应
            if 'choices' in result and len(result['choices']) > 0:
                return result['choices'][0]['message']['content']
            else:
                return f"API 返回格式异常: {result}"
        else:
            return f"API 调用失败 (状态码: {response.status_code}): {response.text}"
            
    except ImportError:
        return "错误: 需要安装 requests 库。运行: pip install requests"
    except Exception as e:
        return f"调用 LLM API 失败: {str(e)}"


def analyze_errors(
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    key_name: Optional[str] = None,
    model: Optional[str] = None,
    limit: Optional[int] = 100,
    llm_api_url: Optional[str] = None,
    llm_api_key: Optional[str] = None,
    llm_model: str = "gpt-4"
) -> Dict[str, Any]:
    """
    完整的错误日志查询与分析流程
    
    Args:
        start_time: 开始时间，格式 "YYYY-MM-DD HH:MM:SS"
        end_time: 结束时间，格式 "YYYY-MM-DD HH:MM:SS"
        key_name: Key Name 筛选（可选）
        model: Model 筛选（可选）
        limit: 限制返回条数
        llm_api_url: LLM API 地址（可选，如果提供则调用 API）
        llm_api_key: LLM API Key（可选）
        llm_model: LLM 模型名称（默认: gpt-4）
    
    Returns:
        包含查询结果和分析结果的字典
    """
    print("=" * 60)
    print("LiteLLM 错误日志查询与分析")
    print("=" * 60)
    
    # 显示查询条件
    print(f"\n查询条件:")
    print(f"  时间范围: {start_time or '最近7天'} 到 {end_time or '现在'}")
    print(f"  Key Name: {key_name or '不筛选'}")
    print(f"  Model: {model or '不筛选'}")
    print(f"  限制条数: {limit}")
    
    # 1. 查询错误日志
    print("\n[1/3] 正在查询错误日志...")
    try:
        error_logs = query_errors(
            start_time=start_time,
            end_time=end_time,
            key_name=key_name,
            model=model,
            limit=limit
        )
        
        if not error_logs:
            print("❌ 未找到错误日志")
            return {
                'error_logs': [],
                'analysis_logs': [],
                'llm_analysis': None,
                'summary': {'total': 0}
            }
        
        print(f"✅ 找到 {len(error_logs)} 条错误日志")
        
        # 2. 准备用于分析的数据
        print("\n[2/3] 正在准备分析数据...")
        analysis_logs = prepare_for_llm(error_logs)
        print(f"✅ 已准备 {len(analysis_logs)} 条日志用于分析")
        
        # 3. 调用大模型分析（如果提供了 API URL）
        llm_result = None
        if llm_api_url:
            print("\n[3/3] 正在调用大模型分析...")
            llm_result = call_llm_api(analysis_logs, llm_api_url, llm_api_key, llm_model)
            print("✅ 大模型分析完成")
        else:
            print("\n[3/3] 跳过 LLM 分析（未提供 API URL）")
            print("提示: 如需调用大模型，请提供 llm_api_url 参数")
        
        # 统计摘要
        summary = {
            'total': len(error_logs),
            'models': {},
            'error_types': {},
            'statuses': {}
        }
        
        for log in error_logs:
            # 统计模型
            m = log.get('model', 'Unknown')
            summary['models'][m] = summary['models'].get(m, 0) + 1
            
            # 统计状态
            s = log.get('status', 'Unknown')
            summary['statuses'][s] = summary['statuses'].get(s, 0) + 1
            
            # 统计错误类型
            error_type = log.get('exception_type', '')
            if not error_type:
                metadata = log.get('metadata', {})
                if isinstance(metadata, dict):
                    error_info = metadata.get('error_information', {})
                    error_type = error_info.get('error_class', '')
            if error_type:
                summary['error_types'][error_type] = summary['error_types'].get(error_type, 0) + 1
        
        # 打印摘要
        print("\n" + "=" * 60)
        print("查询摘要")
        print("=" * 60)
        print(f"总错误数: {summary['total']}")
        print(f"\n按模型统计:")
        for m, count in sorted(summary['models'].items(), key=lambda x: x[1], reverse=True):
            print(f"  {m}: {count}")
        print(f"\n按错误类型统计:")
        for e, count in sorted(summary['error_types'].items(), key=lambda x: x[1], reverse=True):
            print(f"  {e}: {count}")
        
        return {
            'error_logs': error_logs,  # 完整的错误日志列表
            'analysis_logs': analysis_logs,  # 简化后的日志（用于分析）
            'llm_analysis': llm_result,  # LLM 分析结果
            'summary': summary  # 统计摘要
        }
        
    except Exception as e:
        print(f"\n❌ 查询失败: {e}")
        import traceback
        traceback.print_exc()
        return {
            'error_logs': [],
            'analysis_logs': [],
            'llm_analysis': None,
            'summary': {'total': 0},
            'error': str(e)
        }


# ==================== Jupyter 使用示例 ====================

if __name__ == "__main__":
    # 示例 1: 基本查询（不使用 LLM）
    print("示例 1: 基本查询")
    result = analyze_errors(
        start_time="2025-12-22 00:00:00",
        end_time="2025-12-23 23:59:59",
        limit=50
    )
    
    # 查看结果
    print(f"\n查询到 {len(result['error_logs'])} 条错误日志")
    if result['error_logs']:
        print("\n第一条错误日志:")
        print(json.dumps(result['error_logs'][0], indent=2, default=str, ensure_ascii=False))
    
    # 示例 2: 带筛选条件的查询
    # result = analyze_errors(
    #     start_time="2025-12-01 00:00:00",
    #     end_time="2025-12-23 23:59:59",
    #     model="tiny-chat",  # 筛选特定模型
    #     key_name="your_key",  # 筛选特定 key（可选）
    #     limit=100
    # )
    
    # 示例 3: 查询并调用大模型分析
    # result = analyze_errors(
    #     start_time="2025-12-22 00:00:00",
    #     end_time="2025-12-23 23:59:59",
    #     model="tiny-chat",
    #     limit=50,
    #     llm_api_url="https://api.openai.com/v1/chat/completions",
    #     llm_api_key="your-api-key",
    #     llm_model="gpt-4"
    # )
    # 
    # if result['llm_analysis']:
    #     print("\n大模型分析结果:")
    #     print(result['llm_analysis'])

